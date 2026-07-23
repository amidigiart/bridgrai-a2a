"""
Agent de Calibrare — fizica Adler/Kuramoto aplicata la nivel de sistem.

NU calibreaza un singur motor. Calibreaza RELATIA intre agenti.
Foloseste mecanismul Adler (phase-locking) pentru a determina
cat de bine se sincronizeaza agentii intre ei.

Daca Agent de Sens si ACR dau verdicte opuse pe aceeasi intrare,
calibrarea detecteaza dezacordul si recomanda ajustari.

Principiu: K_eff = beta * K_ext >= 1.5 * Delta_omega_max
Daca K_eff e sub prag, agentii se desincronizeaza.

Port: 8007
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bridgrai_a2a.models import (
    AgentCard, AgentCapabilities, Skill, Task, TaskState, TaskStatus,
    Message, Part, PartType,
)
from bridgrai_a2a.server import BaseA2AAgent
from bridgrai_a2a.trust import NotarDeSens

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ukbe_core"))
from ukbe_core.calibration import recommend_beta_min


@dataclass
class SystemCalibration:
    agents_count: int
    avg_response_time: float
    concordance_history: float
    recommended_beta_min: float
    k_effective: float
    synchronized: bool
    phase_lock_ratio: float
    recommendation: str
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "agentsCount": self.agents_count,
            "avgResponseTime": self.avg_response_time,
            "concordanceHistory": self.concordance_history,
            "recommendedBetaMin": self.recommended_beta_min,
            "kEffective": self.k_effective,
            "synchronized": self.synchronized,
            "phaseLockRatio": self.phase_lock_ratio,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp,
        }


def calibrate_system(
    n_agents: int,
    concordance_score: float = 0.8,
    avg_response_ms: float = 100.0,
    delta_omega: float = 0.1,
    k_ext: float = 1.5,
) -> SystemCalibration:
    """Calibreaza parametrii de sistem pe baza starii curente."""
    result = recommend_beta_min(delta_omega, k_ext, safety_margin=1.5)
    beta_min = result["recommended_beta_min"]
    k_eff = beta_min * k_ext

    synchronized = k_eff >= 1.5 * delta_omega and concordance_score >= 0.6
    phase_lock = concordance_score * (1.0 if synchronized else 0.5)

    if synchronized and concordance_score >= 0.8:
        recommendation = "SISTEM SINCRONIZAT — parametrii optimi, nicio ajustare necesara"
    elif synchronized:
        recommendation = f"SINCRONIZAT PARTIAL — concordanta {concordance_score:.2f}, creste K_ext pentru stabilitate"
    elif concordance_score < 0.4:
        recommendation = f"DESINCRONIZAT — concordanta {concordance_score:.2f}, verifica Agent de Sens pentru divergente"
    else:
        recommendation = f"CALIBRARE NECESARA — beta_min={beta_min:.4f}, K_eff={k_eff:.4f}, ajusteaza cuplajul inter-agent"

    return SystemCalibration(
        agents_count=n_agents,
        avg_response_time=avg_response_ms,
        concordance_history=concordance_score,
        recommended_beta_min=beta_min,
        k_effective=k_eff,
        synchronized=synchronized,
        phase_lock_ratio=phase_lock,
        recommendation=recommendation,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


CALIBRATION_CARD = AgentCard(
    name="agent-calibration",
    description="Agent de Calibrare — fizica Adler/Kuramoto la nivel de sistem. "
                "Calibreaza relatia intre agenti, nu agentii individual. "
                "Detecteaza desincronizarea, recomanda ajustari de cuplaj. "
                "K_eff = beta * K_ext >= 1.5 * Delta_omega_max.",
    url="http://localhost:8007",
    version="0.1.0",
    capabilities=AgentCapabilities(streaming=False, push_notifications=False, state_transition_history=True),
    skills=[
        Skill(
            id="system-calibrate",
            name="System Calibration",
            description="Calibreaza parametrii de sistem: beta_min, K_eff, phase lock ratio. "
                        "Returneaza recomandare de ajustare.",
            tags=["calibration", "adler", "kuramoto", "synchronization", "system"],
        ),
        Skill(
            id="sync-check",
            name="Synchronization Check",
            description="Verifica daca agentii sunt sincronizati (phase-locked). "
                        "Foloseste conditia Adler K_eff >= 1.5 * Delta_omega_max.",
            tags=["sync", "check", "phase-lock", "adler"],
        ),
        Skill(
            id="coupling-recommend",
            name="Coupling Recommendation",
            description="Recomanda parametrii de cuplaj inter-agent optimi pe baza "
                        "istoricului de concordanta si raspuns.",
            tags=["coupling", "recommendation", "optimization"],
        ),
    ],
    engine_type="calibration-adler",
)


class CalibrationAgent(BaseA2AAgent):
    def __init__(self, trust: NotarDeSens | None = None):
        super().__init__(CALIBRATION_CARD, trust)
        self._calibration_log: list[SystemCalibration] = []

    async def handle_task(self, task: Task, message: Message) -> Task:
        text = message.text_content().lower()
        n_agents = 5

        concordance = 0.8
        for part in message.parts:
            if part.data and isinstance(part.data, dict):
                concordance = part.data.get("concordance", 0.8)
                n_agents = part.data.get("agents", 5)

        cal = calibrate_system(
            n_agents=n_agents,
            concordance_score=concordance,
        )
        self._calibration_log.append(cal)

        sync_bar = "█" * int(cal.phase_lock_ratio * 10) + "░" * (10 - int(cal.phase_lock_ratio * 10))

        lines = [
            "=" * 50,
            " SYSTEM CALIBRATION — Adler/Kuramoto",
            "=" * 50,
            f"",
            f" Agenti: {cal.agents_count}",
            f" Concordanta: {cal.concordance_history:.2f}",
            f"",
            f" Beta min: {cal.recommended_beta_min:.4f}",
            f" K_eff:    {cal.k_effective:.4f}",
            f" Phase lock: [{sync_bar}] {cal.phase_lock_ratio:.2f}",
            f" Sincronizat: {'DA' if cal.synchronized else 'NU'}",
            f"",
            f" {cal.recommendation}",
            f"",
            f" Timestamp: {cal.timestamp}",
            "=" * 50,
        ]

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
                Part(type=PartType.DATA, data=cal.to_dict()),
            ]),
        )
        return task
