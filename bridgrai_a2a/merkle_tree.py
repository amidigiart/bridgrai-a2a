# -*- coding: utf-8 -*-
"""
Merkle Signature Scheme — extends Lamport for multiple signatures.

A Merkle tree of Lamport public keys allows N signatures from one root.
The root hash is the single "public key" for the entire tree.
Each signature includes the Lamport signature + authentication path.

Quantum-resistant: security = hash function security.
Based on Ralph Merkle (1979) + Lamport (1979).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from .lamport import (
    LamportPrivateKey, LamportPublicKey, LamportSignature,
    generate_keypair, sign as lamport_sign, verify as lamport_verify,
    _sha3, _sha3_hex,
)


def _node_hash(left: bytes, right: bytes) -> bytes:
    return _sha3(left + right)


@dataclass
class MerkleSignatureScheme:
    """
    Pre-generates 2^height Lamport keypairs in a Merkle tree.
    Each leaf is the fingerprint of one Lamport public key.
    The root is the single identity hash — quantum-resistant.
    """
    height: int
    private_keys: list[LamportPrivateKey]
    public_keys: list[LamportPublicKey]
    tree: list[list[bytes]]  # tree[0] = leaves, tree[height] = [root]
    used: list[bool]
    _next_idx: int

    @classmethod
    def generate(cls, height: int = 4) -> "MerkleSignatureScheme":
        n_keys = 2 ** height
        pairs = [generate_keypair() for _ in range(n_keys)]
        private_keys = [p[0] for p in pairs]
        public_keys = [p[1] for p in pairs]

        leaves = [bytes.fromhex(pk.fingerprint()) for pk in public_keys]
        tree = [leaves]
        current = leaves
        for _ in range(height):
            next_level = []
            for i in range(0, len(current), 2):
                next_level.append(_node_hash(current[i], current[i + 1]))
            tree.append(next_level)
            current = next_level

        return cls(
            height=height,
            private_keys=private_keys,
            public_keys=public_keys,
            tree=tree,
            used=[False] * n_keys,
            _next_idx=0,
        )

    @property
    def root(self) -> str:
        return self.tree[self.height][0].hex()

    @property
    def capacity(self) -> int:
        return 2 ** self.height

    @property
    def remaining(self) -> int:
        return sum(1 for u in self.used if not u)

    def _auth_path(self, idx: int) -> list[tuple[bytes, str]]:
        path = []
        for level in range(self.height):
            sibling_idx = idx ^ 1
            side = "right" if idx % 2 == 0 else "left"
            path.append((self.tree[level][sibling_idx], side))
            idx //= 2
        return path

    def sign(self, message: bytes) -> "MerkleSignature":
        if self._next_idx >= self.capacity:
            raise RuntimeError("All Lamport keys exhausted — generate new tree")

        idx = self._next_idx
        if self.used[idx]:
            raise RuntimeError(f"Key {idx} already used — Lamport keys are one-time")

        lsig = lamport_sign(self.private_keys[idx], message)
        auth_path = self._auth_path(idx)
        self.used[idx] = True
        self._next_idx += 1

        return MerkleSignature(
            leaf_idx=idx,
            lamport_sig=lsig,
            lamport_pk=self.public_keys[idx],
            auth_path=auth_path,
            root=self.root,
        )


@dataclass(frozen=True)
class MerkleSignature:
    leaf_idx: int
    lamport_sig: LamportSignature
    lamport_pk: LamportPublicKey
    auth_path: list[tuple[bytes, str]]  # (sibling_hash, "left"|"right")
    root: str

    def to_dict(self) -> dict:
        return {
            "leaf_idx": self.leaf_idx,
            "lamport_sig": self.lamport_sig.to_dict(),
            "lamport_pk": self.lamport_pk.to_dict(),
            "auth_path": [(h.hex(), side) for h, side in self.auth_path],
            "root": self.root,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MerkleSignature":
        return cls(
            leaf_idx=d["leaf_idx"],
            lamport_sig=LamportSignature.from_dict(d["lamport_sig"]),
            lamport_pk=LamportPublicKey.from_dict(d["lamport_pk"]),
            auth_path=[(bytes.fromhex(h), side) for h, side in d["auth_path"]],
            root=d["root"],
        )


def verify_merkle(message: bytes, signature: MerkleSignature) -> bool:
    if not lamport_verify(signature.lamport_pk, message, signature.lamport_sig):
        return False

    current = bytes.fromhex(signature.lamport_pk.fingerprint())
    for sibling, side in signature.auth_path:
        if side == "right":
            current = _node_hash(current, sibling)
        else:
            current = _node_hash(sibling, current)

    return current.hex() == signature.root
