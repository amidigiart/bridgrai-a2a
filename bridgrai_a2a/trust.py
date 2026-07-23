"""
Trust Layer — Notar de Sens si Intentie pentru A2A.

Fiecare mesaj inter-agent:
1. Se hash-uieste (SHA-256)
2. Se semneaza cu cheia Ed25519 a agentului sursa
3. Se verifica de agentul destinatar inainte de procesare
4. Se logheaza in trust ledger (Tezos-ready)

Concordanta: daca doua+ agenti raspund la aceeasi intrebare,
raspunsurile se compara — divergenta > prag = flag.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from .models import Message, TrustEnvelope, hash_message


@dataclass
class AgentIdentity:
    agent_id: str
    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey

    @classmethod
    def generate(cls, agent_id: str) -> AgentIdentity:
        priv = Ed25519PrivateKey.generate()
        return cls(agent_id=agent_id, private_key=priv, public_key=priv.public_key())

    def public_key_hex(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

    def sign(self, data: str) -> str:
        return self.private_key.sign(data.encode("utf-8")).hex()


@dataclass
class TrustRecord:
    source: str
    target: str
    content_hash: str
    verified: bool
    timestamp: str
    task_id: str | None = None
    concordance_score: float | None = None


class NotarDeSens:
    """Trust engine central al platformei BRIDGRAI A2A.

    Certifica SENSUL (hash-ul continutului e consistent) si
    INTENTIA (semnatura agentului e valida = agentul si-a asumat mesajul).
    """

    def __init__(self):
        self._identities: dict[str, AgentIdentity] = {}
        self._public_keys: dict[str, Ed25519PublicKey] = {}
        self._ledger: list[TrustRecord] = []
        self._concordance_store: dict[str, list[tuple[str, str]]] = {}

    def register_agent(self, identity: AgentIdentity) -> None:
        self._identities[identity.agent_id] = identity
        self._public_keys[identity.agent_id] = identity.public_key

    def register_public_key(self, agent_id: str, pub_key_hex: str) -> None:
        pub_bytes = bytes.fromhex(pub_key_hex)
        self._public_keys[agent_id] = Ed25519PublicKey.from_public_bytes(pub_bytes)

    def sign_message(self, agent_id: str, message: Message, target_agent: str) -> TrustEnvelope:
        identity = self._identities.get(agent_id)
        if not identity:
            raise ValueError(f"Agent {agent_id} nu are identitate inregistrata")

        import uuid
        nonce = uuid.uuid4().hex[:16]
        content_hash = hash_message(message, nonce)
        signature = identity.sign(content_hash)
        ts = datetime.now(timezone.utc).isoformat()

        return TrustEnvelope(
            source_agent=agent_id,
            target_agent=target_agent,
            content_hash=content_hash,
            signature_hex=signature,
            timestamp=ts,
            nonce=nonce,
        )

    def verify_envelope(self, envelope: TrustEnvelope, message: Message) -> bool:
        pub_key = self._public_keys.get(envelope.source_agent)
        if not pub_key:
            return False

        recomputed = hash_message(message, envelope.nonce)
        if recomputed != envelope.content_hash:
            return False

        try:
            pub_key.verify(
                bytes.fromhex(envelope.signature_hex),
                envelope.content_hash.encode("utf-8"),
            )
            verified = True
        except InvalidSignature:
            verified = False

        self._ledger.append(TrustRecord(
            source=envelope.source_agent,
            target=envelope.target_agent,
            content_hash=envelope.content_hash,
            verified=verified,
            timestamp=envelope.timestamp,
        ))

        return verified

    def record_for_concordance(self, question_hash: str, agent_id: str, response_hash: str) -> None:
        if question_hash not in self._concordance_store:
            self._concordance_store[question_hash] = []
        self._concordance_store[question_hash].append((agent_id, response_hash))

    def check_concordance(self, question_hash: str) -> dict:
        """Verifica daca agentii au dat raspunsuri concordante.
        Concordanta 1.0 = toti au acelasi hash de raspuns.
        Concordanta < 1.0 = divergenta — necesita investigatie."""
        entries = self._concordance_store.get(question_hash, [])
        if len(entries) < 2:
            return {"concordance": 1.0, "agents": len(entries), "status": "insufficient_data"}

        hashes = [h for _, h in entries]
        unique = len(set(hashes))
        score = 1.0 / unique

        return {
            "concordance": score,
            "agents": len(entries),
            "unique_responses": unique,
            "status": "concordant" if unique == 1 else "divergent",
            "entries": [{"agent": a, "hash": h[:16] + "..."} for a, h in entries],
        }

    def get_ledger(self, limit: int = 100) -> list[dict]:
        return [
            {
                "source": r.source, "target": r.target,
                "contentHash": r.content_hash[:16] + "...",
                "verified": r.verified, "timestamp": r.timestamp,
            }
            for r in self._ledger[-limit:]
        ]

    def master_hash(self) -> str:
        """Hash-ul tuturor inregistrarilor din ledger — ancorat pe Tezos."""
        combined = "|".join(r.content_hash for r in self._ledger)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()
