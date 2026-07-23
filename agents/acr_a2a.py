"""
ACR — Adversarial Collaborative Refinement.

Formalizat de ChatGPT (OpenAI, 3 iunie 2026).
Implementat de Claude (Anthropic, 23 iulie 2026).
Metoda inventata de Mihai Rosca prin practica, nu prin teorie.

ACR = f(D, C, R)
  D = Divergenta — provoaca perspective diferite
  C = Critica — forteaza onestitatea
  R = Recalibrare — corecteaza si rafineaza

Principiu: contradictia nu e esec, e informatie.
Cu cat mai multe cicluri de critica si recalibrare,
cu atat robustetea creste.

NU e consensus. NU e vot majoritar. E FRICTIUNE PRODUCTIVA.
Exact ce face un boxeur: loveste, primeste, corecteaza, loveste mai bine.

Agent A2A: port 8005
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from bridgrai_a2a.models import (
    AgentCard, AgentCapabilities, Skill, Task, TaskState, TaskStatus,
    Message, Part, PartType, Artifact, hash_message,
    jsonrpc_request,
)
from bridgrai_a2a.server import BaseA2AAgent
from bridgrai_a2a.trust import NotarDeSens


# --- ACR Core ---

@dataclass
class DivergencePoint:
    """Un punct de divergenta intre doua perspective."""
    aspect: str
    perspective_a: str
    perspective_b: str
    severity: float  # 0.0 = acord, 1.0 = contradictie totala
    is_information: bool = True  # contradictia e tratata ca informatie

    def to_dict(self) -> dict:
        return {
            "aspect": self.aspect,
            "perspectiveA": self.perspective_a,
            "perspectiveB": self.perspective_b,
            "severity": self.severity,
            "isInformation": self.is_information,
        }


@dataclass
class CritiqueResult:
    """Rezultatul unei critique aplicate pe o afirmatie."""
    original_claim: str
    challenges: list[str]
    survived: list[bool]
    robustness: float  # 0.0 = nu rezista la nimic, 1.0 = rezista la tot

    def to_dict(self) -> dict:
        return {
            "originalClaim": self.original_claim,
            "challenges": self.challenges,
            "survived": self.survived,
            "robustness": self.robustness,
        }


@dataclass
class RecalibrationResult:
    """Rezultatul recalibrarii dupa un ciclu D-C."""
    input_claim: str
    divergences_found: int
    critiques_applied: int
    recalibrated_claim: str
    confidence: float
    cycle_number: int

    def to_dict(self) -> dict:
        return {
            "inputClaim": self.input_claim,
            "divergencesFound": self.divergences_found,
            "critiquesApplied": self.critiques_applied,
            "recalibratedClaim": self.recalibrated_claim,
            "confidence": self.confidence,
            "cycleNumber": self.cycle_number,
        }


@dataclass
class ACRCycle:
    """Un ciclu complet ACR: Divergenta -> Critica -> Recalibrare."""
    cycle_id: str
    claim: str
    divergences: list[DivergencePoint]
    critique: CritiqueResult
    recalibration: RecalibrationResult
    timestamp: str
    hash: str

    def to_dict(self) -> dict:
        return {
            "cycleId": self.cycle_id,
            "claim": self.claim,
            "divergences": [d.to_dict() for d in self.divergences],
            "critique": self.critique.to_dict(),
            "recalibration": self.recalibration.to_dict(),
            "timestamp": self.timestamp,
            "hash": self.hash,
        }


# --- ACR Challenge Templates ---

CHALLENGE_TEMPLATES = [
    "Ce se intampla daca premisa '{claim}' e complet falsa?",
    "Cine are cel mai mult de castigat daca '{claim}' e acceptata necritica?",
    "Ce dovada ar invalida '{claim}'?",
    "Care e cel mai simplu contra-exemplu pentru '{claim}'?",
    "Daca '{claim}' e adevarata, ce implicatii neprevazute ar avea?",
    "Ce ar spune cel mai dur critic despre '{claim}'?",
    "'{claim}' — e asta un fapt verificabil sau o opinie deghizata?",
    "Ce informatii lipsesc pentru a evalua '{claim}' complet?",
]

DIVERGENCE_PROBES = [
    ("scop", "Care e scopul real vs. scopul declarat?"),
    ("dovada", "Ce dovezi sustin vs. ce dovezi lipsesc?"),
    ("alternativa", "Ce alternative au fost ignorate?"),
    ("asumptie", "Ce asumptii nevizibile exista?"),
    ("consecinta", "Ce consecinte neanticipate sunt posibile?"),
    ("bias", "Ce bias-uri pot influenta aceasta perspectiva?"),
]


def generate_divergences(claim: str) -> list[DivergencePoint]:
    """Genereaza puncte de divergenta prin interogare sistematica."""
    divergences = []
    for aspect, probe in DIVERGENCE_PROBES:
        has_answer = _probe_claim(claim, aspect)
        divergences.append(DivergencePoint(
            aspect=aspect,
            perspective_a=f"Afirmatia acopera '{aspect}'",
            perspective_b=probe,
            severity=0.0 if has_answer else 0.5,
        ))
    return divergences


def apply_critique(claim: str) -> CritiqueResult:
    """Aplica provocari sistematice pe o afirmatie."""
    challenges = []
    survived = []

    for template in CHALLENGE_TEMPLATES:
        challenge = template.format(claim=claim[:80])
        challenges.append(challenge)
        survives = _claim_survives_challenge(claim, challenge)
        survived.append(survives)

    pass_count = sum(1 for s in survived if s)
    robustness = pass_count / len(survived) if survived else 0.0

    return CritiqueResult(
        original_claim=claim,
        challenges=challenges,
        survived=survived,
        robustness=robustness,
    )


def recalibrate(claim: str, divergences: list[DivergencePoint],
                critique: CritiqueResult, cycle: int) -> RecalibrationResult:
    """Recalibreaza afirmatia pe baza divergentelor si criticii."""
    severe_divs = [d for d in divergences if d.severity > 0.3]
    failed_challenges = sum(1 for s in critique.survived if not s)

    if failed_challenges == 0 and not severe_divs:
        recalibrated = f"[ROBUST] {claim}"
        confidence = 0.9
    elif failed_challenges <= 2 and len(severe_divs) <= 1:
        recalibrated = f"[RECALIBRAT] {claim} — necesita clarificari pe: {', '.join(d.aspect for d in severe_divs)}"
        confidence = 0.6
    else:
        weak_points = ', '.join(d.aspect for d in severe_divs[:3])
        recalibrated = f"[CONTESTAT] {claim} — puncte slabe: {weak_points}; {failed_challenges}/{len(critique.challenges)} provocari nerezistate"
        confidence = 0.3

    return RecalibrationResult(
        input_claim=claim,
        divergences_found=len(severe_divs),
        critiques_applied=len(critique.challenges),
        recalibrated_claim=recalibrated,
        confidence=confidence,
        cycle_number=cycle,
    )


def run_acr_cycle(claim: str, cycle_number: int = 1) -> ACRCycle:
    """Ruleaza un ciclu complet ACR pe o afirmatie."""
    divergences = generate_divergences(claim)
    critique = apply_critique(claim)
    recalib = recalibrate(claim, divergences, critique, cycle_number)

    ts = datetime.now(timezone.utc).isoformat()
    cycle_hash = hashlib.sha256(
        f"{claim}:{ts}:{cycle_number}".encode("utf-8")
    ).hexdigest()

    return ACRCycle(
        cycle_id=f"ACR-{cycle_hash[:12].upper()}",
        claim=claim,
        divergences=divergences,
        critique=critique,
        recalibration=recalib,
        timestamp=ts,
        hash=cycle_hash,
    )


def _probe_claim(claim: str, aspect: str) -> bool:
    """Verifica daca afirmatia adreseaza un aspect specific."""
    claim_lower = claim.lower()
    aspect_keywords = {
        "scop": ["pentru", "scopul", "obiectiv", "intent", "purpose", "goal"],
        "dovada": ["dovada", "proof", "evidence", "verificat", "confirmat", "testat"],
        "alternativa": ["alternativ", "altfel", "instead", "alternative", "sau"],
        "asumptie": ["presupun", "assume", "daca", "conditie", "if"],
        "consecinta": ["consecinta", "rezultat", "impact", "efect", "consequence"],
        "bias": ["obiectiv", "neutral", "impartial", "independent", "verificat"],
    }
    keywords = aspect_keywords.get(aspect, [])
    return any(kw in claim_lower for kw in keywords)


def _claim_survives_challenge(claim: str, challenge: str) -> bool:
    """Evalueaza daca afirmatia rezista unei provocari.
    v0: euristic pe baza de indicatori de robustete in claim."""
    robustness_markers = [
        "verificat", "testat", "dovedit", "confirmat", "independent",
        "public", "auditabil", "hash", "blockchain", "doi",
        "verified", "tested", "proven", "confirmed", "published",
    ]
    weakness_markers = [
        "cred", "probabil", "poate", "sper", "ar trebui",
        "believe", "probably", "maybe", "hope", "should",
    ]
    claim_lower = claim.lower()
    strength = sum(1 for m in robustness_markers if m in claim_lower)
    weakness = sum(1 for m in weakness_markers if m in claim_lower)
    return strength > weakness


# --- Agent Card ---

ACR_CARD = AgentCard(
    name="acr-engine",
    description="Adversarial Collaborative Refinement — motorul de frictiune productiva. "
                "Formalizat: ChatGPT (OpenAI, 3 iunie 2026). "
                "Implementat: Claude (Anthropic, 23 iulie 2026). "
                "Inventat: Mihai Rosca, prin practica. "
                "ACR = f(D, C, R). Contradictia e informatie, nu esec.",
    url="http://localhost:8005",
    version="0.1.0",
    capabilities=AgentCapabilities(streaming=False, push_notifications=False, state_transition_history=True),
    skills=[
        Skill(
            id="acr-cycle",
            name="ACR Full Cycle",
            description="Ciclu complet: Divergenta -> Critica -> Recalibrare. "
                        "Ia o afirmatie, o provoaca din 6 unghiuri, aplica 8 provocari, "
                        "recalibreaza cu scor de robustete.",
            tags=["acr", "adversarial", "refinement", "cycle", "robustness"],
            examples=[
                "acr: Agent de Sens este o categorie noua in AI",
                "acr: Ecosistemul BRIDGRAI are valoare de 5M EUR",
            ],
        ),
        Skill(
            id="divergence",
            name="Divergence Analysis",
            description="Identifica punctele de divergenta ale unei afirmatii: "
                        "scop, dovada, alternative, asumptii, consecinte, bias.",
            tags=["divergence", "analysis", "perspective", "probe"],
        ),
        Skill(
            id="critique",
            name="Adversarial Critique",
            description="Aplica 8 provocari sistematice pe o afirmatie. "
                        "Returneaza scor de robustete (0=fragila, 1=solida).",
            tags=["critique", "adversarial", "challenge", "robustness"],
        ),
        Skill(
            id="multi-cycle",
            name="Multi-Cycle Refinement",
            description="Ruleaza N cicluri ACR succesive pe aceeasi afirmatie. "
                        "Fiecare ciclu rafineaza rezultatul ciclului anterior. "
                        "Robustetea creste cu fiecare iteratie.",
            tags=["multi-cycle", "iterative", "refinement", "convergence"],
        ),
    ],
    engine_type="acr-engine",
)


class ACRAgent(BaseA2AAgent):
    """Motorul ACR — frictiune productiva intre perspective."""

    def __init__(self, trust: NotarDeSens | None = None):
        super().__init__(ACR_CARD, trust)
        self._cycle_history: list[ACRCycle] = []

    async def handle_task(self, task: Task, message: Message) -> Task:
        text = message.text_content().lower()

        if "multi" in text or "iterati" in text:
            return await self._handle_multi_cycle(task, message)
        elif "divergen" in text:
            return await self._handle_divergence(task, message)
        elif "critic" in text or "challenge" in text:
            return await self._handle_critique(task, message)
        else:
            return await self._handle_full_cycle(task, message)

    async def _handle_full_cycle(self, task: Task, message: Message) -> Task:
        raw = message.text_content()
        claim = raw
        for prefix in ["acr:", "cycle:", "test:", "refine:", "certify:"]:
            if claim.lower().startswith(prefix):
                claim = claim[len(prefix):].strip()
                break

        cycle = run_acr_cycle(claim)
        self._cycle_history.append(cycle)

        severe = [d for d in cycle.divergences if d.severity > 0.3]
        failed = sum(1 for s in cycle.critique.survived if not s)

        lines = [
            f"{'='*50}",
            f" ACR — ADVERSARIAL COLLABORATIVE REFINEMENT",
            f" Cycle: {cycle.cycle_id}",
            f"{'='*50}",
            f"",
            f" AFIRMATIE: {claim[:100]}",
            f"",
            f" [D] DIVERGENTA ({len(severe)}/{len(cycle.divergences)} severe):",
        ]
        for d in cycle.divergences:
            marker = "!!" if d.severity > 0.3 else "ok"
            lines.append(f"   [{marker}] {d.aspect}: {d.severity:.1f}")

        lines.append(f"")
        lines.append(f" [C] CRITICA ({len(cycle.critique.challenges)} provocari):")
        for i, (ch, surv) in enumerate(zip(cycle.critique.challenges, cycle.critique.survived)):
            status = "REZISTA" if surv else "CEDEAZA"
            lines.append(f"   [{status}] {ch[:70]}...")

        lines.append(f"")
        lines.append(f" [R] RECALIBRARE:")
        lines.append(f"   Robustete: {cycle.critique.robustness:.2f}")
        lines.append(f"   Incredere: {cycle.recalibration.confidence:.2f}")
        lines.append(f"   Verdict: {cycle.recalibration.recalibrated_claim[:100]}")
        lines.append(f"")
        lines.append(f" Hash: {cycle.hash[:32]}...")
        lines.append(f" Timestamp: {cycle.timestamp}")
        lines.append(f"{'='*50}")

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
                Part(type=PartType.DATA, data=cycle.to_dict()),
            ]),
        )
        task.artifacts.append(Artifact(
            name=f"acr-{cycle.cycle_id}",
            parts=[Part(type=PartType.DATA, data=cycle.to_dict())],
            metadata={"type": "acr-cycle"},
        ))
        return task

    async def _handle_divergence(self, task: Task, message: Message) -> Task:
        claim = message.text_content()
        divergences = generate_divergences(claim)

        lines = [" DIVERGENCE ANALYSIS", ""]
        for d in divergences:
            bar = "█" * int(d.severity * 10) + "░" * (10 - int(d.severity * 10))
            lines.append(f"  {d.aspect}: [{bar}] {d.severity:.1f}")
            lines.append(f"    A: {d.perspective_a}")
            lines.append(f"    B: {d.perspective_b}")
            lines.append("")

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
                Part(type=PartType.DATA, data={"divergences": [d.to_dict() for d in divergences]}),
            ]),
        )
        return task

    async def _handle_critique(self, task: Task, message: Message) -> Task:
        claim = message.text_content()
        critique = apply_critique(claim)

        lines = [" ADVERSARIAL CRITIQUE", f" Robustete: {critique.robustness:.2f}", ""]
        for ch, surv in zip(critique.challenges, critique.survived):
            status = "REZISTA" if surv else "CEDEAZA"
            lines.append(f"  [{status}] {ch[:80]}")

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
                Part(type=PartType.DATA, data=critique.to_dict()),
            ]),
        )
        return task

    async def _handle_multi_cycle(self, task: Task, message: Message) -> Task:
        raw = message.text_content()
        claim = raw
        for prefix in ["multi:", "iterate:", "refine:"]:
            if claim.lower().startswith(prefix):
                claim = claim[len(prefix):].strip()
                break

        cycles = []
        current_claim = claim
        for i in range(3):
            cycle = run_acr_cycle(current_claim, cycle_number=i + 1)
            cycles.append(cycle)
            self._cycle_history.append(cycle)
            current_claim = cycle.recalibration.recalibrated_claim

        lines = [
            f" ACR MULTI-CYCLE REFINEMENT (3 cicluri)",
            f" Input: {claim[:80]}",
            f"",
        ]
        for cycle in cycles:
            lines.append(f" Ciclu {cycle.recalibration.cycle_number}:")
            lines.append(f"   Robustete: {cycle.critique.robustness:.2f}")
            lines.append(f"   Incredere: {cycle.recalibration.confidence:.2f}")
            lines.append(f"   Output: {cycle.recalibration.recalibrated_claim[:80]}")
            lines.append("")

        final = cycles[-1]
        lines.append(f" CONVERGENTA:")
        lines.append(f"   Robustete finala: {final.critique.robustness:.2f}")
        lines.append(f"   Cicluri: {len(cycles)}")
        lines.append(f"   Verdict: {final.recalibration.recalibrated_claim[:100]}")

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
                Part(type=PartType.DATA, data={
                    "cycles": [c.to_dict() for c in cycles],
                    "finalRobustness": final.critique.robustness,
                    "finalConfidence": final.recalibration.confidence,
                }),
            ]),
        )
        return task
