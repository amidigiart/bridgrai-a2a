"""
Agent Maestru — orchestrator cognitiv al platformei BRIDGRAI A2A.

NU e un router. NU e un load balancer. E un CREIER.

Primeste orice input si decide:
1. CE tip de procesare necesita (safety? sens? provocare? calibrare?)
2. CARE agenti trebuie chemati
3. IN CE ORDINE (pipeline-ul optimal)
4. Executa pipeline-ul
5. Returneaza rezultat unificat cu lant de provenienta complet

VALOARE:
- Transforma 8 unelte independente intr-un SISTEM
- Orice non-tehnician poate trimite o intrebare si primeste
  raspuns certificat, provocat, calibrat, verificat
- Nimeni altcineva nu are orchestrare COGNITIVA cu trust layer

UNDE SE INCADREAZA:
  Input → MAESTRU → [Sens → CASP → ACR → Concordance] → Output certificat
  Maestrul e DEASUPRA tuturor, dar nu INLOCUIESTE pe nimeni.
  Fiecare agent ramane independent. Maestrul doar DECIDE ordinea.

Port: 8009
"""
from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from bridgrai_a2a.models import (
    AgentCard, AgentCapabilities, Skill, Task, TaskState, TaskStatus,
    Message, Part, PartType, jsonrpc_request,
)
from bridgrai_a2a.server import BaseA2AAgent
from bridgrai_a2a.trust import NotarDeSens


class ProcessingNeed(str, Enum):
    SAFETY = "safety"
    MEANING = "meaning"
    CHALLENGE = "challenge"
    CALIBRATION = "calibration"
    CONCORDANCE = "concordance"
    SECURITY = "security"
    HERITAGE = "heritage"
    SIMULATION = "simulation"


AGENT_CAPABILITIES = {
    "agent-de-sens": {
        "needs": [ProcessingNeed.MEANING],
        "description": "Certifica SENSUL si INTENTIA — TVE 6-pillar",
        "priority": 1,
    },
    "casp-dual-engine": {
        "needs": [ProcessingNeed.SAFETY],
        "description": "Validare semantica — empathy, non-harm, transparency",
        "priority": 2,
    },
    "acr-engine": {
        "needs": [ProcessingNeed.CHALLENGE],
        "description": "Provocare adversariala — ACR = f(D,C,R)",
        "priority": 3,
    },
    "agent-concordance": {
        "needs": [ProcessingNeed.CONCORDANCE],
        "description": "Verificare multi-agent — P(confab) = p^N",
        "priority": 4,
    },
    "agent-calibration": {
        "needs": [ProcessingNeed.CALIBRATION],
        "description": "Calibrare Adler/Kuramoto — sync check",
        "priority": 5,
    },
    "hasn-security": {
        "needs": [ProcessingNeed.SECURITY],
        "description": "Securitate — threat assessment, monitoring",
        "priority": 6,
    },
    "ukbe-core": {
        "needs": [ProcessingNeed.SIMULATION],
        "description": "Simulare Kuramoto — rezonanta, notarizare",
        "priority": 7,
    },
    "agent-heritage": {
        "needs": [ProcessingNeed.HERITAGE],
        "description": "Custode transgenerational — inventar, Mars check",
        "priority": 8,
    },
}

SAFETY_KEYWORDS = [
    "safe", "harm", "danger", "violent", "toxic", "hate",
    "sigur", "pericol", "violenta", "toxic",
]
MEANING_KEYWORDS = [
    "certif", "sens", "intentie", "meaning", "intent", "trust",
    "manipul", "honest", "genuine", "authen",
]
CHALLENGE_KEYWORDS = [
    "claim", "afirmatie", "prove", "dovedeste", "challenge",
    "contest", "critica", "robust", "weak", "slab",
]
SECURITY_KEYWORDS = [
    "security", "securitate", "threat", "amenintare", "attack",
    "breach", "vulnerab", "hack",
]
HERITAGE_KEYWORDS = [
    "patrick", "mostenire", "heritage", "mars", "transgenerational",
    "inventar", "custode",
]
CALIBRATION_KEYWORDS = [
    "calibr", "sync", "phase", "kuramoto", "adler",
    "parametr", "coupling",
]
SIMULATION_KEYWORDS = [
    "simulat", "kuramoto", "oscilator", "resonan",
]


@dataclass
class PipelineStep:
    agent: str
    reason: str
    order: int

    def to_dict(self) -> dict:
        return {"agent": self.agent, "reason": self.reason, "order": self.order}


@dataclass
class OrchestratedResult:
    input_hash: str
    pipeline: list[PipelineStep]
    results: dict[str, dict]
    unified_verdict: str
    confidence: float
    provenance_chain: list[str]
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "inputHash": self.input_hash,
            "pipeline": [s.to_dict() for s in self.pipeline],
            "results": self.results,
            "unifiedVerdict": self.unified_verdict,
            "confidence": self.confidence,
            "provenanceChain": self.provenance_chain,
            "timestamp": self.timestamp,
        }


def detect_needs(text: str) -> list[ProcessingNeed]:
    """Analizeaza textul si decide ce tip de procesare necesita."""
    text_lower = text.lower()
    needs: list[ProcessingNeed] = []

    if any(k in text_lower for k in MEANING_KEYWORDS):
        needs.append(ProcessingNeed.MEANING)
    if any(k in text_lower for k in SAFETY_KEYWORDS):
        needs.append(ProcessingNeed.SAFETY)
    if any(k in text_lower for k in CHALLENGE_KEYWORDS):
        needs.append(ProcessingNeed.CHALLENGE)
    if any(k in text_lower for k in SECURITY_KEYWORDS):
        needs.append(ProcessingNeed.SECURITY)
    if any(k in text_lower for k in HERITAGE_KEYWORDS):
        needs.append(ProcessingNeed.HERITAGE)
    if any(k in text_lower for k in CALIBRATION_KEYWORDS):
        needs.append(ProcessingNeed.CALIBRATION)
    if any(k in text_lower for k in SIMULATION_KEYWORDS):
        needs.append(ProcessingNeed.SIMULATION)

    if not needs:
        needs = [ProcessingNeed.MEANING, ProcessingNeed.SAFETY]

    return needs


def build_pipeline(needs: list[ProcessingNeed], mode: str = "standard") -> list[PipelineStep]:
    """Construieste pipeline-ul optimal de agenti."""
    steps: list[PipelineStep] = []

    if mode == "full":
        for agent_id, info in sorted(
            AGENT_CAPABILITIES.items(), key=lambda x: x[1]["priority"]
        ):
            steps.append(PipelineStep(
                agent=agent_id,
                reason=info["description"],
                order=len(steps) + 1,
            ))
        return steps

    matched_agents = set()
    for need in needs:
        for agent_id, info in AGENT_CAPABILITIES.items():
            if need in info["needs"]:
                matched_agents.add(agent_id)

    for agent_id in sorted(
        matched_agents,
        key=lambda a: AGENT_CAPABILITIES[a]["priority"],
    ):
        steps.append(PipelineStep(
            agent=agent_id,
            reason=AGENT_CAPABILITIES[agent_id]["description"],
            order=len(steps) + 1,
        ))

    return steps


MAESTRU_CARD = AgentCard(
    name="agent-maestru",
    description="Agent Maestru — orchestrator cognitiv. Primeste orice input, "
                "decide care agenti trebuie chemati si in ce ordine, "
                "executa pipeline-ul, returneaza rezultat unificat cu "
                "lant de provenienta complet. Creierul platformei.",
    url="http://localhost:8009",
    version="0.1.0",
    capabilities=AgentCapabilities(
        streaming=False,
        push_notifications=True,
        state_transition_history=True,
    ),
    skills=[
        Skill(
            id="orchestrate",
            name="Full Orchestration",
            description="Trimite input prin pipeline-ul optimal de agenti. "
                        "Autodetecteaza nevoile (safety, sens, provocare, etc), "
                        "construieste ordinea, executa, unifica rezultatele.",
            tags=["orchestration", "pipeline", "cognitive", "maestru", "auto"],
        ),
        Skill(
            id="pipeline-plan",
            name="Pipeline Planning",
            description="Analizeaza un input si returneaza pipeline-ul PLANIFICAT "
                        "(fara executie). Arata care agenti ar fi chemati si de ce.",
            tags=["planning", "pipeline", "analysis", "dry-run"],
        ),
        Skill(
            id="full-audit",
            name="Full Ecosystem Audit",
            description="Trimite inputul prin TOTI 8 agentii, in ordinea de prioritate. "
                        "Rezultat maxim cu provenienta completa.",
            tags=["audit", "full", "all-agents", "maximum"],
        ),
        Skill(
            id="ecosystem-map",
            name="Ecosystem Map",
            description="Returneaza harta completa a ecosistemului: "
                        "ce agent face ce, unde se incadreaza, ce valoare are.",
            tags=["map", "ecosystem", "value", "positioning"],
        ),
    ],
    engine_type="orchestrator-cognitive",
)


class MaestruAgent(BaseA2AAgent):
    def __init__(
        self,
        trust: NotarDeSens | None = None,
        agents: dict | None = None,
    ):
        super().__init__(MAESTRU_CARD, trust)
        self._agents = agents or {}
        self._orchestrations: list[OrchestratedResult] = []

    async def handle_task(self, task: Task, message: Message) -> Task:
        text = message.text_content()
        text_lower = text.lower()

        if "map" in text_lower or "harta" in text_lower or "ecosystem" in text_lower:
            return await self._handle_map(task)
        elif "plan" in text_lower and ("pipeline" in text_lower or "analiz" in text_lower):
            return await self._handle_plan(task, text)
        elif "full audit" in text_lower or "audit complet" in text_lower or "toti" in text_lower:
            return await self._handle_orchestrate(task, text, mode="full")
        else:
            return await self._handle_orchestrate(task, text, mode="standard")

    async def _handle_plan(self, task: Task, text: str) -> Task:
        needs = detect_needs(text)
        pipeline = build_pipeline(needs)

        lines = [
            "=" * 55,
            " MAESTRU — PIPELINE PLANNING (dry run)",
            "=" * 55,
            "",
            f" Input: {text[:80]}{'...' if len(text)>80 else ''}",
            f" Nevoi detectate: {', '.join(n.value for n in needs)}",
            f" Agenti in pipeline: {len(pipeline)}",
            "",
        ]
        for step in pipeline:
            lines.append(f"  [{step.order}] {step.agent}")
            lines.append(f"      {step.reason}")
        lines.append("")
        lines.append(" Executie: NU (dry run)")
        lines.append("=" * 55)

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
                Part(type=PartType.DATA, data={
                    "needs": [n.value for n in needs],
                    "pipeline": [s.to_dict() for s in pipeline],
                    "executed": False,
                }),
            ]),
        )
        return task

    async def _handle_orchestrate(
        self, task: Task, text: str, mode: str = "standard"
    ) -> Task:
        ts = datetime.now(timezone.utc).isoformat()
        input_hash = hashlib.sha256(text.encode()).hexdigest()

        needs = detect_needs(text)
        pipeline = build_pipeline(needs, mode=mode)

        results: dict[str, dict] = {}
        provenance: list[str] = []
        total_score = 0.0
        agent_count = 0

        for step in pipeline:
            agent = self._agents.get(step.agent)
            if agent is None:
                results[step.agent] = {
                    "status": "SKIPPED",
                    "reason": "Agent not connected to Maestru",
                }
                provenance.append(f"[{step.order}] {step.agent}: SKIPPED")
                continue

            try:
                agent_msg = Message(
                    role="user",
                    parts=[Part(type=PartType.TEXT, text=text)],
                )
                rpc = jsonrpc_request("tasks/send", {"message": agent_msg.to_dict()})
                result = await agent._process_rpc(rpc)

                task_result = result.get("result", {})
                status = task_result.get("status", {})
                state = status.get("state", "unknown")
                agent_response = status.get("message", {})

                response_text = ""
                response_data = {}
                for part in agent_response.get("parts", []):
                    if part.get("text"):
                        response_text = part["text"]
                    if part.get("data"):
                        response_data = part["data"]

                score = response_data.get("concordanceScore",
                        response_data.get("overallScore",
                        response_data.get("phaseLockRatio",
                        1.0 if state == "completed" else 0.0)))

                results[step.agent] = {
                    "status": state,
                    "score": score,
                    "summary": response_text[:200] if response_text else "",
                    "data": response_data,
                }
                provenance.append(
                    f"[{step.order}] {step.agent}: {state} (score={score:.2f})"
                )
                total_score += float(score)
                agent_count += 1

            except Exception as e:
                results[step.agent] = {
                    "status": "ERROR",
                    "error": str(e)[:200],
                }
                provenance.append(f"[{step.order}] {step.agent}: ERROR — {str(e)[:60]}")

        confidence = total_score / agent_count if agent_count > 0 else 0.0

        if confidence >= 0.8:
            verdict = "CERTIFIED — pipeline complet, incredere ridicata"
        elif confidence >= 0.5:
            verdict = "PARTIAL — unii agenti au semnalat probleme"
        elif confidence >= 0.3:
            verdict = "CONTESTAT — divergente semnificative in pipeline"
        else:
            verdict = "RESPINS — incredere prea scazuta, necesita revizuire"

        orchestrated = OrchestratedResult(
            input_hash=input_hash,
            pipeline=pipeline,
            results=results,
            unified_verdict=verdict,
            confidence=confidence,
            provenance_chain=provenance,
            timestamp=ts,
        )
        self._orchestrations.append(orchestrated)

        conf_bar = int(confidence * 20)
        bar = "█" * conf_bar + "░" * (20 - conf_bar)

        lines = [
            "=" * 55,
            " MAESTRU — ORCHESTRATED RESULT",
            "=" * 55,
            "",
            f" Mode: {mode.upper()}",
            f" Agenti in pipeline: {len(pipeline)}",
            f" Executati: {agent_count}",
            "",
            " PROVENANCE CHAIN:",
        ]
        for p in provenance:
            lines.append(f"   {p}")

        lines.extend([
            "",
            f" Confidence: [{bar}] {confidence:.2f}",
            f" Verdict: {verdict}",
            "",
            f" Input hash: {input_hash[:32]}...",
            f" Timestamp: {ts}",
            "=" * 55,
        ])

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
                Part(type=PartType.DATA, data=orchestrated.to_dict()),
            ]),
        )
        return task

    async def _handle_map(self, task: Task) -> Task:
        lines = [
            "=" * 60,
            " BRIDGRAI A2A — ECOSYSTEM MAP",
            " Unde se incadreaza fiecare. Ce valoare are.",
            "=" * 60,
            "",
            " LAYER 4: ORCHESTRARE",
            " ┌─────────────────────────────────────────────────┐",
            " │  MAESTRU (:8009) — creierul platformei          │",
            " │  Decide ce agent, in ce ordine, pentru ce scop  │",
            " │  Valoare: transforma 8 unelte in 1 SISTEM       │",
            " └──────────────────────┬────────────────────────────┘",
            "                        │",
            " LAYER 3: VERIFICARE    │",
            " ┌──────────────────────┴────────────────────────────┐",
            " │ CONCORDANCE (:8006)  │  CALIBRATION (:8007)      │",
            " │ Verifica ACORDUL     │  Verifica SINCRONIZAREA   │",
            " │ P(confab) = p^N      │  K_eff >= 1.5*dw          │",
            " │ Valoare: anti-       │  Valoare: detecteaza      │",
            " │ confabulare          │  dezacordul intre agenti  │",
            " │ matematica           │  inainte sa devina criza  │",
            " └──────────────────────┴────────────────────────────┘",
            "                        │",
            " LAYER 2: CERTIFICARE   │",
            " ┌──────────────────────┴────────────────────────────┐",
            " │ AGENT DE SENS (:8004) │  ACR ENGINE (:8005)      │",
            " │ Certifica SENSUL +    │  Provoaca ADVERSARIAL    │",
            " │ INTENTIA (TVE 6-axis) │  ACR = f(D,C,R)          │",
            " │ Valoare: NIMENI NU    │  Valoare: daca rezista   │",
            " │ ARE ASTA — categorie  │  la 8 provocari, e solid │",
            " │ noua in AI            │  Inventat Mihai, formal. │",
            " │                       │  ChatGPT, impl. Claude   │",
            " └──────────────────────┴────────────────────────────┘",
            "                        │",
            " LAYER 1: FUNDATIE      │",
            " ┌──────────────────────┴────────────────────────────┐",
            " │ UKBE (:8001)  │  CASP (:8002)  │  HASN (:8003)  │",
            " │ Fizica:       │  Safety:        │  Securitate:   │",
            " │ Kuramoto +    │  empathy +      │  monitoring +  │",
            " │ Kalman +      │  non_harm +     │  threat assess │",
            " │ Adler + Ed25519 transparency    │  + Node.js     │",
            " │ Valoare: cel  │  Valoare: nicio │  Valoare: nicio│",
            " │ mai testat    │  iesire fara    │  usa deschisa  │",
            " │ motor (102/102)  validare       │  fara stiinta  │",
            " └──────────────────────┴────────────────────────────┘",
            "                        │",
            " LAYER 0: MOSTENIRE     │",
            " ┌──────────────────────┴────────────────────────────┐",
            " │ HERITAGE (:8008) — custode transgenerational     │",
            " │ 16 active digitale, Mars 2% bandwidth            │",
            " │ Valoare: tot ce e deasupra PERSISTA               │",
            " │ Fiul Patrick poate verifica independent ORICE     │",
            " └───────────────────────────────────────────────────┘",
            "",
            " TRUST: Ed25519 sign + SHA-256 hash + Tezos-ready",
            " PROTOCOL: Google A2A (JSON-RPC 2.0)",
            " VALIDARI: Gemini (P=10^-28) + Claude + ChatGPT",
            "",
            " Total: 9 agenti, 5 layere, 97 Tezos entries",
            " Formula: S(M) = R",
            "=" * 60,
        ]

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
            ]),
        )
        return task
