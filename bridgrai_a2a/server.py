"""
A2A Server — implementare JSON-RPC 2.0 conforme cu protocolul Google A2A.

Fiecare engine BRIDGRAI mosteneste BaseA2AAgent si implementeaza handle_task().
Serverul expune:
- GET  /.well-known/agent.json  → Agent Card
- POST /a2a                      → JSON-RPC 2.0 endpoint
- GET  /a2a/trust/ledger         → Trust ledger (extensie BRIDGRAI)
"""
from __future__ import annotations
import json
import logging
from abc import ABC, abstractmethod

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    AgentCard, Task, TaskState, TaskStatus, Message, Part, PartType,
    jsonrpc_response, jsonrpc_error,
)
from .trust import NotarDeSens, AgentIdentity

logger = logging.getLogger("bridgrai.a2a")


class BaseA2AAgent(ABC):
    """Clasa de baza pe care fiecare engine o extinde."""

    def __init__(self, card: AgentCard, trust: NotarDeSens | None = None):
        self.card = card
        self.trust = trust
        self.identity: AgentIdentity | None = None
        self._tasks: dict[str, Task] = {}

        if trust:
            self.identity = AgentIdentity.generate(card.name)
            trust.register_agent(self.identity)

    @abstractmethod
    async def handle_task(self, task: Task, message: Message) -> Task:
        """Proceseaza un task primit prin A2A. Returneaza task-ul actualizat."""

    async def _process_rpc(self, body: dict) -> dict:
        method = body.get("method", "")
        params = body.get("params", {})
        req_id = body.get("id")

        if method == "tasks/send":
            return await self._handle_send(req_id, params)
        elif method == "tasks/get":
            return self._handle_get(req_id, params)
        elif method == "tasks/cancel":
            return self._handle_cancel(req_id, params)
        else:
            return jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    async def _handle_send(self, req_id: str | None, params: dict) -> dict:
        task_id = params.get("id")
        msg_data = params.get("message", {})
        trust_envelope = params.get("x-bridgrai-trust")

        message = Message.from_dict(msg_data)

        if trust_envelope and self.trust:
            from .models import TrustEnvelope as TE
            envelope = TE.from_dict(trust_envelope)
            verified = self.trust.verify_envelope(envelope, message)
            if not verified:
                return jsonrpc_error(req_id, -32000, "Trust verification failed — mesajul nu a trecut Notar de Sens")

        if task_id and task_id in self._tasks:
            task = self._tasks[task_id]
        else:
            task = Task(id=task_id or Task().id)
            self._tasks[task.id] = task

        task.history.append(message)
        task.status = TaskStatus(state=TaskState.WORKING)

        try:
            task = await self.handle_task(task, message)
        except Exception as e:
            logger.exception("Agent %s failed on task %s", self.card.name, task.id)
            task.status = TaskStatus(
                state=TaskState.FAILED,
                message=Message(role="agent", parts=[Part(type=PartType.TEXT, text=str(e))]),
            )

        self._tasks[task.id] = task
        return jsonrpc_response(req_id, task.to_dict())

    def _handle_get(self, req_id: str | None, params: dict) -> dict:
        task_id = params.get("id", "")
        task = self._tasks.get(task_id)
        if not task:
            return jsonrpc_error(req_id, -32002, f"Task not found: {task_id}")
        return jsonrpc_response(req_id, task.to_dict())

    def _handle_cancel(self, req_id: str | None, params: dict) -> dict:
        task_id = params.get("id", "")
        task = self._tasks.get(task_id)
        if not task:
            return jsonrpc_error(req_id, -32002, f"Task not found: {task_id}")
        task.status = TaskStatus(state=TaskState.CANCELED)
        return jsonrpc_response(req_id, task.to_dict())

    def create_app(self) -> FastAPI:
        app = FastAPI(title=f"A2A: {self.card.name}", version=self.card.version)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
        )

        @app.get("/.well-known/agent.json")
        async def agent_card():
            return self.card.to_dict()

        @app.post("/a2a")
        async def a2a_endpoint(request: Request):
            body = await request.json()

            if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
                return JSONResponse(
                    jsonrpc_error(None, -32600, "Invalid JSON-RPC 2.0 request"),
                    status_code=400,
                )
            return JSONResponse(await self._process_rpc(body))

        if self.trust:
            @app.get("/a2a/trust/ledger")
            async def trust_ledger():
                return {"ledger": self.trust.get_ledger(), "masterHash": self.trust.master_hash()}

        @app.get("/health")
        async def health():
            return {
                "agent": self.card.name,
                "status": "ok",
                "tasks": len(self._tasks),
                "trust": self.identity.public_key_hex()[:16] + "..." if self.identity else None,
            }

        return app
