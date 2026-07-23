"""
A2A Client — trimite taskuri catre alti agenti prin protocolul A2A.

Suporta:
- Discovery (citeste Agent Card)
- Send task (JSON-RPC 2.0)
- Trust envelope (semnatura Notar de Sens)
- Concordance check (trimite aceeasi intrebare la N agenti, compara)
"""
from __future__ import annotations
import hashlib
import json
from typing import Any

import httpx

from .models import (
    AgentCard, Message, Part, PartType, Task, TrustEnvelope,
    jsonrpc_request, hash_message,
)
from .trust import NotarDeSens, AgentIdentity


class A2AClient:
    def __init__(self, trust: NotarDeSens | None = None, identity: AgentIdentity | None = None):
        self.trust = trust
        self.identity = identity
        self._http = httpx.AsyncClient(timeout=30.0)
        self._known_agents: dict[str, AgentCard] = {}

    async def discover(self, base_url: str) -> AgentCard:
        url = f"{base_url.rstrip('/')}/.well-known/agent.json"
        resp = await self._http.get(url)
        resp.raise_for_status()
        data = resp.json()

        card = AgentCard(
            name=data["name"],
            description=data["description"],
            url=data["url"],
            version=data.get("version", "1.0.0"),
            skills=[],
        )
        self._known_agents[card.name] = card
        return card

    async def send_task(
        self,
        agent_url: str,
        message: Message,
        task_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"message": message.to_dict()}
        if task_id:
            params["id"] = task_id
        if session_id:
            params["sessionId"] = session_id

        if self.trust and self.identity:
            agent_name = self._resolve_agent_name(agent_url)
            envelope = self.trust.sign_message(self.identity.agent_id, message, agent_name)
            params["x-bridgrai-trust"] = envelope.to_dict()

        rpc = jsonrpc_request("tasks/send", params)
        url = f"{agent_url.rstrip('/')}/a2a"
        resp = await self._http.post(url, json=rpc)
        resp.raise_for_status()
        return resp.json()

    async def get_task(self, agent_url: str, task_id: str) -> dict:
        rpc = jsonrpc_request("tasks/get", {"id": task_id})
        url = f"{agent_url.rstrip('/')}/a2a"
        resp = await self._http.post(url, json=rpc)
        resp.raise_for_status()
        return resp.json()

    async def send_to_multiple(
        self,
        agent_urls: list[str],
        message: Message,
    ) -> dict:
        """Trimite aceeasi intrebare la mai multi agenti.
        Returneaza raspunsurile + concordance check."""
        question_hash = hash_message(message)
        results = {}

        for url in agent_urls:
            try:
                resp = await self.send_task(url, message)
                result = resp.get("result", {})
                status = result.get("status", {})
                agent_msg = status.get("message", {})
                response_text = ""
                for part in agent_msg.get("parts", []):
                    if part.get("text"):
                        response_text += part["text"]

                response_hash = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
                agent_name = self._resolve_agent_name(url)
                results[agent_name] = {
                    "response": response_text,
                    "hash": response_hash,
                    "task": result,
                }

                if self.trust:
                    self.trust.record_for_concordance(question_hash, agent_name, response_hash)
            except Exception as e:
                results[url] = {"error": str(e)}

        concordance = {}
        if self.trust:
            concordance = self.trust.check_concordance(question_hash)

        return {"responses": results, "concordance": concordance}

    def _resolve_agent_name(self, url: str) -> str:
        for name, card in self._known_agents.items():
            if card.url.rstrip("/") == url.rstrip("/"):
                return name
        return url

    async def close(self):
        await self._http.aclose()
