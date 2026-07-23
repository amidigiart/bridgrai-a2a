"""
A2A Protocol Models — conforme cu specificatia Google Agent-to-Agent.

Structuri JSON-RPC 2.0 pentru comunicare inter-agent:
- AgentCard: identitate + capabilitati agent
- Task: unitatea de lucru delegata intre agenti
- Message/Part: continutul schimbat intre agenti
- TrustEnvelope: extensie BRIDGRAI — fiecare mesaj e semnat si verificabil
"""
from __future__ import annotations
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class PartType(str, Enum):
    TEXT = "text"
    FILE = "file"
    DATA = "data"


@dataclass
class Part:
    type: PartType
    text: str | None = None
    data: dict | None = None
    file_name: str | None = None
    file_bytes: bytes | None = None

    def to_dict(self) -> dict:
        d = {"type": self.type.value}
        if self.text is not None:
            d["text"] = self.text
        if self.data is not None:
            d["data"] = self.data
        if self.file_name is not None:
            d["fileName"] = self.file_name
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Part:
        return cls(
            type=PartType(d["type"]),
            text=d.get("text"),
            data=d.get("data"),
            file_name=d.get("fileName"),
        )


@dataclass
class Message:
    role: str  # "user" | "agent"
    parts: list[Part]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "parts": [p.to_dict() for p in self.parts],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Message:
        return cls(
            role=d["role"],
            parts=[Part.from_dict(p) for p in d["parts"]],
            metadata=d.get("metadata", {}),
        )

    def text_content(self) -> str:
        return " ".join(p.text for p in self.parts if p.text)


@dataclass
class Artifact:
    name: str
    parts: list[Part]
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "parts": [p.to_dict() for p in self.parts],
            "metadata": self.metadata,
        }


@dataclass
class TaskStatus:
    state: TaskState
    message: Message | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"state": self.state.value, "timestamp": self.timestamp}
        if self.message:
            d["message"] = self.message.to_dict()
        return d


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str | None = None
    status: TaskStatus = field(default_factory=lambda: TaskStatus(state=TaskState.SUBMITTED))
    artifacts: list[Artifact] = field(default_factory=list)
    history: list[Message] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "id": self.id,
            "status": self.status.to_dict(),
            "artifacts": [a.to_dict() for a in self.artifacts],
            "history": [m.to_dict() for m in self.history],
            "metadata": self.metadata,
        }
        if self.session_id:
            d["sessionId"] = self.session_id
        return d


@dataclass
class Skill:
    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {"id": self.id, "name": self.name, "description": self.description, "tags": self.tags}
        if self.examples:
            d["examples"] = self.examples
        return d


@dataclass
class AgentCapabilities:
    streaming: bool = False
    push_notifications: bool = False
    state_transition_history: bool = True

    def to_dict(self) -> dict:
        return {
            "streaming": self.streaming,
            "pushNotifications": self.push_notifications,
            "stateTransitionHistory": self.state_transition_history,
        }


@dataclass
class AgentCard:
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    default_input_modes: list[str] = field(default_factory=lambda: ["text"])
    default_output_modes: list[str] = field(default_factory=lambda: ["text"])
    skills: list[Skill] = field(default_factory=list)
    provider: str = "BRIDGRAI Foundation"
    authentication: dict = field(default_factory=lambda: {"schemes": ["none"]})
    # extensie BRIDGRAI
    trust_endpoint: str | None = None
    engine_type: str | None = None

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities.to_dict(),
            "defaultInputModes": self.default_input_modes,
            "defaultOutputModes": self.default_output_modes,
            "skills": [s.to_dict() for s in self.skills],
            "provider": {"organization": self.provider},
            "authentication": self.authentication,
        }
        if self.trust_endpoint:
            d["x-bridgrai-trust"] = self.trust_endpoint
        if self.engine_type:
            d["x-bridgrai-engine"] = self.engine_type
        return d


# --- BRIDGRAI Trust Extensions ---

@dataclass
class TrustEnvelope:
    """Fiecare mesaj A2A trece prin Notar de Sens.
    Hash-ul continutului + semnatura agentului sursa = proof verificabil."""
    source_agent: str
    target_agent: str
    content_hash: str
    signature_hex: str
    timestamp: str
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex[:16])

    def to_dict(self) -> dict:
        return {
            "sourceAgent": self.source_agent,
            "targetAgent": self.target_agent,
            "contentHash": self.content_hash,
            "signatureHex": self.signature_hex,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TrustEnvelope:
        return cls(
            source_agent=d["sourceAgent"],
            target_agent=d["targetAgent"],
            content_hash=d["contentHash"],
            signature_hex=d["signatureHex"],
            timestamp=d["timestamp"],
            nonce=d.get("nonce", ""),
        )


def hash_message(message: Message, nonce: str = "") -> str:
    payload = json.dumps(
        {"role": message.role, "parts": [p.to_dict() for p in message.parts], "nonce": nonce},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --- JSON-RPC 2.0 helpers ---

def jsonrpc_request(method: str, params: dict, req_id: str | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id or str(uuid.uuid4()),
        "method": method,
        "params": params,
    }


def jsonrpc_response(req_id: str, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id: str | None, code: int, message: str, data: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}
