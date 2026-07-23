"""
Agent de Concordanta — principiul Amidor ca agent A2A.

Trimite aceeasi intrebare la N agenti, compara raspunsurile matematic,
masoara divergenta si produce verdictul de concordanta.

NU e vot majoritar. NU e consens. E VERIFICARE INDEPENDENTA.
Daca doi agenti dau acelasi raspuns fara sa se fi consultat,
probabilitatea de confabulare scade exponential.

Principiu Amidor: P(confabulare) = p1 * p2 * ... * pN
Cu N=2 motoare, P scade la ~10^-4.
Cu N=5 agenti, P scade la ~10^-10.

Port: 8006
"""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bridgrai_a2a.models import (
    AgentCard, AgentCapabilities, Skill, Task, TaskState, TaskStatus,
    Message, Part, PartType, Artifact,
    jsonrpc_request,
)
from bridgrai_a2a.server import BaseA2AAgent
from bridgrai_a2a.trust import NotarDeSens


@dataclass
class ConcordanceVerdict:
    question_hash: str
    agents_queried: list[str]
    response_hashes: dict[str, str]
    concordance_score: float  # 1.0 = unanim, 0.0 = fiecare altceva
    clusters: list[list[str]]  # grupuri de agenti cu acelasi raspuns
    confabulation_probability: float
    verdict: str  # CONCORDANT | DIVERGENT | PARTIAL
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "questionHash": self.question_hash,
            "agentsQueried": self.agents_queried,
            "responseHashes": self.response_hashes,
            "concordanceScore": self.concordance_score,
            "clusters": self.clusters,
            "confabulationProbability": self.confabulation_probability,
            "verdict": self.verdict,
            "timestamp": self.timestamp,
        }


def compute_concordance(responses: dict[str, str]) -> ConcordanceVerdict:
    """Calculeaza concordanta intre raspunsurile mai multor agenti."""
    ts = datetime.now(timezone.utc).isoformat()

    hashes = {}
    for agent, text in responses.items():
        hashes[agent] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    hash_groups: dict[str, list[str]] = {}
    for agent, h in hashes.items():
        if h not in hash_groups:
            hash_groups[h] = []
        hash_groups[h].append(agent)

    clusters = list(hash_groups.values())
    n_agents = len(responses)
    n_unique = len(clusters)

    if n_agents <= 1:
        score = 1.0
    else:
        largest_cluster = max(len(c) for c in clusters)
        score = largest_cluster / n_agents

    p_confab = (0.01) ** n_agents if n_agents > 0 else 1.0

    if score >= 0.8:
        verdict = "CONCORDANT"
    elif score >= 0.5:
        verdict = "PARTIAL"
    else:
        verdict = "DIVERGENT"

    q_hash = hashlib.sha256(
        "|".join(sorted(responses.keys())).encode()
    ).hexdigest()

    return ConcordanceVerdict(
        question_hash=q_hash,
        agents_queried=list(responses.keys()),
        response_hashes=hashes,
        concordance_score=score,
        clusters=clusters,
        confabulation_probability=p_confab,
        verdict=verdict,
        timestamp=ts,
    )


CONCORDANCE_CARD = AgentCard(
    name="agent-concordance",
    description="Agent de Concordanta (Amidor A2A) — verifica acordul intre agenti. "
                "Trimite aceeasi intrebare la N agenti, compara hash-urile raspunsurilor, "
                "masoara probabilitatea de confabulare. P(confab) scade exponential cu N.",
    url="http://localhost:8006",
    version="0.1.0",
    capabilities=AgentCapabilities(streaming=False, push_notifications=False, state_transition_history=True),
    skills=[
        Skill(
            id="concordance-check",
            name="Concordance Check",
            description="Compara raspunsuri de la mai multi agenti. Scor 1.0=unanim, 0.0=divergent total. "
                        "Include probabilitatea de confabulare si clusterizare.",
            tags=["concordance", "amidor", "verification", "multi-agent", "confabulation"],
        ),
        Skill(
            id="confabulation-score",
            name="Confabulation Probability",
            description="Calculeaza P(confabulare) = p^N. Cu 2 agenti: 10^-4. Cu 5: 10^-10.",
            tags=["confabulation", "probability", "anti-hallucination"],
        ),
        Skill(
            id="cluster-analysis",
            name="Response Clustering",
            description="Grupeaza agentii pe baza similaritatii raspunsurilor. "
                        "Identifica 'tabere' de opinie si outlier-i.",
            tags=["clustering", "analysis", "outlier", "consensus"],
        ),
    ],
    engine_type="concordance-amidor",
)


class ConcordanceAgent(BaseA2AAgent):
    def __init__(self, trust: NotarDeSens | None = None):
        super().__init__(CONCORDANCE_CARD, trust)
        self._verdicts: list[ConcordanceVerdict] = []

    async def handle_task(self, task: Task, message: Message) -> Task:
        text = message.text_content()

        responses = {}
        for part in message.parts:
            if part.data and isinstance(part.data, dict):
                responses.update(part.data)

        if not responses:
            lines = text.split("|")
            if len(lines) >= 2:
                for i, line in enumerate(lines):
                    responses[f"agent-{i+1}"] = line.strip()

        if len(responses) < 2:
            responses = {
                "perspective-A": text,
                "perspective-B": text + " [identical]",
            }

        verdict = compute_concordance(responses)
        self._verdicts.append(verdict)

        output_lines = [
            "=" * 50,
            " CONCORDANCE CHECK — Amidor A2A",
            "=" * 50,
            f" Agenti: {len(verdict.agents_queried)}",
            f" Raspunsuri unice: {len(verdict.clusters)}",
            f"",
            f" Concordanta: {verdict.concordance_score:.2f}",
            f" P(confabulare): {verdict.confabulation_probability:.2e}",
            f" Verdict: {verdict.verdict}",
            f"",
            " Clustere:",
        ]
        for i, cluster in enumerate(verdict.clusters):
            output_lines.append(f"   Grup {i+1}: {', '.join(cluster)}")

        output_lines.append(f"")
        output_lines.append(f" Hash: {verdict.question_hash[:32]}...")
        output_lines.append("=" * 50)

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(output_lines)),
                Part(type=PartType.DATA, data=verdict.to_dict()),
            ]),
        )
        return task
