"""
UKBE Core — A2A Agent Wrapper.

Expune motorul Kuramoto+RSI, notary-ul, DID-ul si calibrarea ca skill-uri A2A.
Alte agenti pot delega catre UKBE pentru:
- Simulare Kuramoto (analiza coerenta interna)
- Notarizare (semnare + verificare documente)
- Generare/rezolvare DID
- Calibrare beta_min
- State snapshot (starea curenta a motorului)
"""
from __future__ import annotations
import json

from bridgrai_a2a.models import (
    AgentCard, AgentCapabilities, Skill, Task, TaskState, TaskStatus,
    Message, Part, PartType, Artifact,
)
from bridgrai_a2a.server import BaseA2AAgent
from bridgrai_a2a.trust import NotarDeSens

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ukbe_core"))

from ukbe_core.engine import UKBEEngine, UKBEConfig
from ukbe_core.calibration import recommend_beta_min
from ukbe_core import notary as notary_module


UKBE_CARD = AgentCard(
    name="ukbe-core",
    description="Unified Kuramoto-RSI Bridging Engine — motorul de simulare a coerentei "
                "interne (Kuramoto) cuplat dinamic cu estimarea intentiei umane (Kalman+RSI). "
                "Include notary Ed25519, DID, si calibrare Adler.",
    url="http://localhost:8001",
    version="0.1.0",
    capabilities=AgentCapabilities(streaming=False, push_notifications=False, state_transition_history=True),
    skills=[
        Skill(
            id="kuramoto-simulate",
            name="Kuramoto Simulation",
            description="Ruleaza o simulare Kuramoto cu N oscilatori si proxy uman. "
                        "Returneaza RSI, Phi intern/extern, alpha/beta.",
            tags=["kuramoto", "simulation", "coherence", "rsi", "physics"],
            examples=["simulate 100 steps with default config"],
        ),
        Skill(
            id="notarize",
            name="Notarize Document",
            description="Semneaza si notarizeaza un document/intentie cu Ed25519. "
                        "Returneaza hash SHA-256 + semnatura verificabila.",
            tags=["notary", "sign", "verify", "ed25519", "hash"],
            examples=["notarize intent='AI alignment research' actor='bridgrai'"],
        ),
        Skill(
            id="verify-notarization",
            name="Verify Notarization",
            description="Verifica independent o notarizare existenta.",
            tags=["notary", "verify", "trust"],
        ),
        Skill(
            id="calibrate",
            name="Calibrate Beta Min",
            description="Recomanda beta_min optim pe baza mecanismului Adler. "
                        "Input: delta_omega_max, K_ext.",
            tags=["calibration", "adler", "beta", "physics"],
        ),
        Skill(
            id="state-snapshot",
            name="Engine State Snapshot",
            description="Returneaza starea curenta completa a motorului: phi_intern, "
                        "entropia H, RSI, lock_ratio.",
            tags=["state", "snapshot", "monitoring"],
        ),
    ],
    engine_type="ukbe-core",
)


class UKBEAgent(BaseA2AAgent):
    def __init__(self, trust: NotarDeSens | None = None):
        super().__init__(UKBE_CARD, trust)
        self._engine: UKBEEngine | None = None
        self._notary_keys: tuple[bytes, bytes] | None = None

    def _ensure_engine(self) -> UKBEEngine:
        if self._engine is None:
            self._engine = UKBEEngine(UKBEConfig())
        return self._engine

    def _ensure_notary_keys(self) -> tuple[bytes, bytes]:
        if self._notary_keys is None:
            self._notary_keys = notary_module.generate_keypair()
        return self._notary_keys

    async def handle_task(self, task: Task, message: Message) -> Task:
        text = message.text_content().lower()

        if "simulate" in text or "kuramoto" in text or "step" in text:
            return await self._handle_simulate(task, message)
        elif "notarize" in text or "sign" in text:
            return await self._handle_notarize(task, message)
        elif "verify" in text:
            return await self._handle_verify(task, message)
        elif "calibrat" in text or "beta" in text:
            return await self._handle_calibrate(task, message)
        elif "state" in text or "snapshot" in text:
            return await self._handle_snapshot(task, message)
        else:
            return await self._handle_snapshot(task, message)

    async def _handle_simulate(self, task: Task, message: Message) -> Task:
        engine = self._ensure_engine()
        import numpy as np
        steps = 100
        proxy_series = np.sin(np.linspace(0, 4 * np.pi, steps)) + np.random.normal(0, 0.1, steps)
        results = engine.run(proxy_series.tolist())
        final = results[-1]
        summary = (
            f"Simulare Kuramoto completata: {steps} pasi.\n"
            f"RSI final: {final['RSI']:.4f}\n"
            f"Phi intern: {final['Phi_intern']:.4f}\n"
            f"Phi extern: {final['Phi_extern']:.4f}\n"
            f"Alpha: {final['alpha']:.4f}, Beta: {final['beta']:.4f}\n"
            f"Psi (dezaliniere): {final['psi']:.4f} rad"
        )
        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text=summary),
                Part(type=PartType.DATA, data={"final_step": final, "total_steps": steps}),
            ]),
        )
        return task

    async def _handle_notarize(self, task: Task, message: Message) -> Task:
        priv, pub = self._ensure_notary_keys()
        text = message.text_content()
        record = notary_module.notarize(
            intent=text, actor="a2a-agent", qid="a2a-task", private_key_bytes=priv,
        )
        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text=f"Notarizat: {record.content_hash[:32]}..."),
                Part(type=PartType.DATA, data={
                    "contentHash": record.content_hash,
                    "signature": record.signature_hex,
                    "publicKey": pub.hex(),
                    "timestamp": record.timestamp,
                }),
            ]),
        )
        return task

    async def _handle_verify(self, task: Task, message: Message) -> Task:
        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="Verificare necesita record complet (hash + signature + public key). Trimite ca DataPart."),
            ]),
        )
        return task

    async def _handle_calibrate(self, task: Task, message: Message) -> Task:
        result = recommend_beta_min(delta_omega_max=0.1, K_ext=1.5, safety_margin=1.5)
        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text=f"Beta min recomandat: {result['beta_min']:.4f}"),
                Part(type=PartType.DATA, data=result),
            ]),
        )
        return task

    async def _handle_snapshot(self, task: Task, message: Message) -> Task:
        engine = self._ensure_engine()
        snapshot = engine.get_state_snapshot()
        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text=(
                    f"UKBE State: Phi={snapshot['phi_intern']:.4f}, "
                    f"H={snapshot['h']:.4f}, RSI={snapshot['rsi']:.4f}, "
                    f"Lock={snapshot['lock_ratio']:.2%}"
                )),
                Part(type=PartType.DATA, data=snapshot),
            ]),
        )
        return task
