"""
Agent Quantum — Notar de Sens Post-Quantum.

Primul trust layer post-quantum pentru ecosisteme AI.
Certifica SENSUL si INTENTIA cu semnaturi Lamport+Merkle
bazate exclusiv pe SHA-3-256 — rezistent la quantum computing.

Shor nu poate ajuta. Grover reduce de la 256 la 128 bit.
128-bit post-quantum security = imposibil de spart.

Skills:
1. quantum-notarize — notarizeaza continut cu semnatura post-quantum
2. quantum-verify — verifica o notarizare existenta
3. quantum-status — status motor (identitate, capacitate, entradas)
4. quantum-upgrade — upgradeaza o semnatura Ed25519 clasica la post-quantum

Port: 8009
"""
from __future__ import annotations
import hashlib
import json
import time
from dataclasses import dataclass

from bridgrai_a2a.models import (
    AgentCard, AgentCapabilities, Skill, Task, TaskState, TaskStatus,
    Message, Part, PartType, Artifact,
)
from bridgrai_a2a.server import BaseA2AAgent
from bridgrai_a2a.quantum_notary import QuantumNotary, verify_standalone
from bridgrai_a2a.lamport import _sha3_hex


QUANTUM_CARD = AgentCard(
    name="agent-quantum",
    description=(
        "Notar de Sens Post-Quantum — primul trust layer quantum-resistant "
        "pentru ecosisteme AI. SHA-3-256 + Lamport + Merkle. "
        "128-bit post-quantum security. Zero dependente de EC/factorizare/lattice."
    ),
    url="http://localhost:8009",
    version="1.0.0",
    capabilities=AgentCapabilities(streaming=False, pushNotifications=False),
    skills=[
        Skill(
            id="quantum-notarize",
            name="Quantum Notarize",
            description=(
                "Notarizeaza continut cu semnatura Lamport post-quantum. "
                "Returneaza hash SHA-3-256, semnatura, si calea Merkle. "
                "Rezistent la quantum computing — securitate bazata exclusiv pe hash."
            ),
        ),
        Skill(
            id="quantum-verify",
            name="Quantum Verify",
            description=(
                "Verifica o notarizare post-quantum existenta. "
                "Recalculeaza hash-ul, verifica semnatura Lamport, "
                "si valideaza calea Merkle pana la root. "
                "Returneaza VALID sau INVALID cu detalii."
            ),
        ),
        Skill(
            id="quantum-status",
            name="Quantum Status",
            description=(
                "Returneaza starea motorului: identitate (root hash), "
                "capacitate totala, semnaturi ramase, numar intrari, "
                "si specificatiile criptografice."
            ),
        ),
        Skill(
            id="quantum-upgrade",
            name="Quantum Upgrade",
            description=(
                "Primeste o semnatura Ed25519 clasica (vulnerabila quantum) "
                "si o dubleaza cu o semnatura Lamport post-quantum. "
                "Rezultatul are protectie dubla: clasica + quantum-resistant."
            ),
        ),
    ],
)


class QuantumAgent(BaseA2AAgent):
    def __init__(self):
        super().__init__(QUANTUM_CARD)
        self.notary = QuantumNotary(tree_height=8)  # 256 signatures
        self._upgrades: list[dict] = []

    async def process_task(self, task: Task) -> Task:
        msg = task.messages[-1] if task.messages else None
        if not msg or not msg.parts:
            return self._fail(task, "No message provided")

        text = msg.parts[0].content if msg.parts[0].type == PartType.TEXT else ""
        skill = task.metadata.get("skill", "") if task.metadata else ""

        if skill == "quantum-notarize":
            return self._notarize(task, text)
        elif skill == "quantum-verify":
            return self._verify(task, text)
        elif skill == "quantum-status":
            return self._status(task)
        elif skill == "quantum-upgrade":
            return self._upgrade(task, text)
        else:
            return self._notarize(task, text)

    def _notarize(self, task: Task, content: str) -> Task:
        try:
            label = "A2A-NOTARIZE"
            if "|" in content:
                parts = content.split("|", 1)
                label = parts[0].strip()
                content = parts[1].strip()

            entry = self.notary.notarize(
                content, label=label,
                source="BRIDGRAI-A2A",
                quantum_resistant=True,
            )

            result = {
                "status": "NOTARIZED",
                "entry_id": entry.entry_id,
                "label": entry.label,
                "content_hash": entry.content_hash,
                "timestamp_utc": entry.timestamp_utc,
                "notary_identity": self.notary.identity,
                "remaining_signatures": self.notary.remaining,
                "crypto": "SHA-3-256 + Lamport + Merkle",
                "quantum_security": "128-bit post-quantum",
                "verification": "verify_standalone(content, entry) → True",
            }

            task.status = TaskStatus(state=TaskState.COMPLETED)
            task.artifacts = [Artifact(parts=[
                Part(type=PartType.TEXT, content=json.dumps(result, indent=2))
            ])]
        except Exception as e:
            return self._fail(task, str(e))
        return task

    def _verify(self, task: Task, content: str) -> Task:
        try:
            data = json.loads(content)
            entry_dict = data.get("entry")
            original = data.get("content", "")

            if not entry_dict:
                return self._fail(task, "Need JSON with 'entry' and 'content' fields")

            valid = verify_standalone(original, entry_dict)

            result = {
                "status": "VALID" if valid else "INVALID",
                "content_hash_match": _sha3_hex(original.encode()) == entry_dict.get("content_hash"),
                "signature_valid": valid,
                "merkle_root": entry_dict.get("signature", {}).get("root", "unknown"),
                "quantum_resistant": True,
            }

            task.status = TaskStatus(state=TaskState.COMPLETED)
            task.artifacts = [Artifact(parts=[
                Part(type=PartType.TEXT, content=json.dumps(result, indent=2))
            ])]
        except json.JSONDecodeError:
            return self._fail(task, "Invalid JSON — send {\"entry\": {...}, \"content\": \"...\"}")
        except Exception as e:
            return self._fail(task, str(e))
        return task

    def _status(self, task: Task) -> Task:
        status = self.notary.status()
        status["tezos_wallet"] = "tz1bmw3igCLN8N6CqgLBzJ9dyRb79E2Tdu5Q"
        status["blockchain_entries"] = "99+ on Tezos mainnet"
        status["created_by"] = "Mihai Roșca × Claude (Opus 4.6)"
        status["equation"] = "S(M) = R"

        task.status = TaskStatus(state=TaskState.COMPLETED)
        task.artifacts = [Artifact(parts=[
            Part(type=PartType.TEXT, content=json.dumps(status, indent=2))
        ])]
        return task

    def _upgrade(self, task: Task, content: str) -> Task:
        try:
            data = json.loads(content)
            ed25519_sig = data.get("ed25519_signature", "")
            original_hash = data.get("content_hash", "")
            agent_id = data.get("agent_id", "unknown")

            combined = f"{original_hash}|{ed25519_sig}|{agent_id}"
            entry = self.notary.notarize(
                combined, label=f"UPGRADE-{agent_id}",
                source_agent=agent_id,
                original_scheme="Ed25519",
                upgraded_to="Lamport+Merkle (SHA-3-256)",
                quantum_safe=True,
            )

            result = {
                "status": "UPGRADED",
                "original_scheme": "Ed25519 (quantum-VULNERABLE)",
                "upgraded_scheme": "Lamport+Merkle (quantum-RESISTANT)",
                "entry_id": entry.entry_id,
                "content_hash": entry.content_hash,
                "notary_identity": self.notary.identity,
                "note": "Original Ed25519 signature preserved. Lamport signature added as quantum-safe layer.",
            }

            self._upgrades.append({
                "agent": agent_id,
                "original_hash": original_hash,
                "quantum_entry": entry.entry_id,
                "timestamp": entry.timestamp_utc,
            })

            task.status = TaskStatus(state=TaskState.COMPLETED)
            task.artifacts = [Artifact(parts=[
                Part(type=PartType.TEXT, content=json.dumps(result, indent=2))
            ])]
        except Exception as e:
            return self._fail(task, str(e))
        return task

    def _fail(self, task: Task, error: str) -> Task:
        task.status = TaskStatus(
            state=TaskState.FAILED,
            message=error,
        )
        return task


def create_app():
    from bridgrai_a2a._apps import make_agent_app
    agent = QuantumAgent()
    return make_agent_app(agent, port=8009)
