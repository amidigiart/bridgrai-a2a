# -*- coding: utf-8 -*-
"""
Lamport One-Time Signature — provably quantum-resistant.

Security relies ONLY on the pre-image resistance of the hash function.
No number theory, no EC/ECC, no lattices.
Shor's algorithm cannot help. Grover's reduces SHA-3-256 to 128-bit — still unbreakable.

This is the simplest quantum-resistant signature scheme that exists.
Invented by Leslie Lamport (1979). Proven secure under hash function assumptions.
"""
from __future__ import annotations

import hashlib
import os
import json
from dataclasses import dataclass


HASH_BYTES = 32  # SHA-3-256 → 256 bits → 32 bytes
HASH_BITS = HASH_BYTES * 8  # 256


def _sha3(data: bytes) -> bytes:
    return hashlib.sha3_256(data).digest()


def _sha3_hex(data: bytes) -> str:
    return hashlib.sha3_256(data).hexdigest()


@dataclass(frozen=True)
class LamportPrivateKey:
    """256 pairs of 256-bit random secrets. One-time use only."""
    pairs: list[tuple[bytes, bytes]]  # 256 pairs, each (sk0, sk1)

    def public_key(self) -> "LamportPublicKey":
        return LamportPublicKey(
            pairs=[(_sha3(sk0), _sha3(sk1)) for sk0, sk1 in self.pairs]
        )

    def to_dict(self) -> dict:
        return {
            "pairs": [(sk0.hex(), sk1.hex()) for sk0, sk1 in self.pairs]
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LamportPrivateKey":
        return cls(
            pairs=[(bytes.fromhex(p[0]), bytes.fromhex(p[1])) for p in d["pairs"]]
        )


@dataclass(frozen=True)
class LamportPublicKey:
    """256 pairs of hash(secret). Safe to publish."""
    pairs: list[tuple[bytes, bytes]]  # 256 pairs, each (pk0, pk1)

    def fingerprint(self) -> str:
        flat = b"".join(pk0 + pk1 for pk0, pk1 in self.pairs)
        return _sha3_hex(flat)

    def to_dict(self) -> dict:
        return {
            "pairs": [(pk0.hex(), pk1.hex()) for pk0, pk1 in self.pairs],
            "fingerprint": self.fingerprint(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LamportPublicKey":
        return cls(
            pairs=[(bytes.fromhex(p[0]), bytes.fromhex(p[1])) for p in d["pairs"]]
        )


@dataclass(frozen=True)
class LamportSignature:
    """256 revealed secrets, one per bit of the message hash."""
    parts: list[bytes]  # 256 secrets

    def to_dict(self) -> dict:
        return {"parts": [p.hex() for p in self.parts]}

    @classmethod
    def from_dict(cls, d: dict) -> "LamportSignature":
        return cls(parts=[bytes.fromhex(p) for p in d["parts"]])


def generate_keypair() -> tuple[LamportPrivateKey, LamportPublicKey]:
    pairs = [(os.urandom(HASH_BYTES), os.urandom(HASH_BYTES)) for _ in range(HASH_BITS)]
    sk = LamportPrivateKey(pairs=pairs)
    return sk, sk.public_key()


def sign(private_key: LamportPrivateKey, message: bytes) -> LamportSignature:
    msg_hash = _sha3(message)
    parts = []
    for i in range(HASH_BITS):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)
        bit = (msg_hash[byte_idx] >> bit_idx) & 1
        parts.append(private_key.pairs[i][bit])
    return LamportSignature(parts=parts)


def verify(public_key: LamportPublicKey, message: bytes, signature: LamportSignature) -> bool:
    if len(signature.parts) != HASH_BITS:
        return False
    msg_hash = _sha3(message)
    for i in range(HASH_BITS):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)
        bit = (msg_hash[byte_idx] >> bit_idx) & 1
        if _sha3(signature.parts[i]) != public_key.pairs[i][bit]:
            return False
    return True
