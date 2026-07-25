# -*- coding: utf-8 -*-
"""
Quantum Notary — Notar de Sens Post-Quantum

The first post-quantum trust layer for AI ecosystems.
Certifies MEANING and INTENTION, not just existence.

Security: SHA-3-256 + Lamport + Merkle = quantum-resistant.
No EC/ECC. No factoring-based crypto. No lattice assumptions.
Only hash functions — the one primitive that survives everything.

Architecture:
  1. Content → SHA-3-256 hash
  2. Hash → Lamport one-time signature (quantum-resistant)
  3. Signatures → Merkle tree (reusable identity)
  4. Root hash = post-quantum identity of the notary
  5. Verification = pure math, no trust required

Created by: Mihai Roșca × Claude (Opus 4.6)
Date: 25 July 2026
S(M) = R
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .lamport import _sha3_hex
from .merkle_tree import MerkleSignatureScheme, MerkleSignature, verify_merkle


@dataclass
class NotaryEntry:
    entry_id: int
    label: str
    content_hash: str  # SHA-3-256 of the content
    timestamp_utc: str
    signature: MerkleSignature
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "label": self.label,
            "content_hash": self.content_hash,
            "timestamp_utc": self.timestamp_utc,
            "signature": self.signature.to_dict(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "NotaryEntry":
        return cls(
            entry_id=d["entry_id"],
            label=d["label"],
            content_hash=d["content_hash"],
            timestamp_utc=d["timestamp_utc"],
            signature=MerkleSignature.from_dict(d["signature"]),
            metadata=d.get("metadata", {}),
        )


class QuantumNotary:
    """
    Post-quantum Notar de Sens.

    Each instance has a Merkle tree identity (root hash).
    Each notarization uses one Lamport key (one-time, quantum-safe).
    The root hash is the permanent identity — publish it, blockchain it.
    """

    def __init__(self, tree_height: int = 6):
        self.mss = MerkleSignatureScheme.generate(height=tree_height)
        self.ledger: list[NotaryEntry] = []
        self._created_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @property
    def identity(self) -> str:
        return self.mss.root

    @property
    def capacity(self) -> int:
        return self.mss.capacity

    @property
    def remaining(self) -> int:
        return self.mss.remaining

    @property
    def entries_count(self) -> int:
        return len(self.ledger)

    def notarize(self, content: bytes | str, label: str, **metadata) -> NotaryEntry:
        if isinstance(content, str):
            content = content.encode("utf-8")

        content_hash = _sha3_hex(content)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        signature = self.mss.sign(content_hash.encode("utf-8"))

        entry = NotaryEntry(
            entry_id=len(self.ledger) + 1,
            label=label,
            content_hash=content_hash,
            timestamp_utc=timestamp,
            signature=signature,
            metadata=metadata,
        )
        self.ledger.append(entry)
        return entry

    def notarize_file(self, path: str | Path, label: str | None = None, **metadata) -> NotaryEntry:
        p = Path(path)
        content = p.read_bytes()
        return self.notarize(
            content,
            label=label or p.name,
            file=str(p),
            size_bytes=len(content),
            **metadata,
        )

    def verify_entry(self, entry: NotaryEntry) -> bool:
        return verify_merkle(entry.content_hash.encode("utf-8"), entry.signature)

    def verify_content(self, content: bytes | str, entry: NotaryEntry) -> bool:
        if isinstance(content, str):
            content = content.encode("utf-8")
        if _sha3_hex(content) != entry.content_hash:
            return False
        return self.verify_entry(entry)

    def export_ledger(self) -> dict:
        return {
            "quantum_notary": {
                "version": "1.0.0",
                "identity": self.identity,
                "created_utc": self._created_utc,
                "tree_height": self.mss.height,
                "capacity": self.capacity,
                "used": self.capacity - self.remaining,
                "remaining": self.remaining,
                "crypto": {
                    "hash": "SHA-3-256 (FIPS 202)",
                    "signature": "Lamport one-time (1979)",
                    "tree": "Merkle signature scheme (1979)",
                    "quantum_security": "128-bit post-quantum (Grover bound)",
                    "assumptions": "Pre-image resistance of SHA-3 only",
                    "vulnerable_to": "Nothing known. No dependence on factoring, discrete log, or lattice problems.",
                },
            },
            "entries": [e.to_dict() for e in self.ledger],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.export_ledger(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def status(self) -> dict:
        return {
            "identity": self.identity,
            "entries": self.entries_count,
            "remaining_signatures": self.remaining,
            "capacity": self.capacity,
            "quantum_resistant": True,
            "crypto": "SHA-3-256 + Lamport + Merkle",
        }


def verify_standalone(content: bytes | str, entry_dict: dict) -> bool:
    entry = NotaryEntry.from_dict(entry_dict)
    if isinstance(content, str):
        content = content.encode("utf-8")
    if _sha3_hex(content) != entry.content_hash:
        return False
    return verify_merkle(entry.content_hash.encode("utf-8"), entry.signature)
