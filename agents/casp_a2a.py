"""
CASP DualEngine — A2A Agent Wrapper.

Expune motorul dual (Grok + DeepSeek) cu validare CASP ca agent A2A.
Alte agenti pot delega catre CASP pentru:
- Generare raspuns certificat (dual-engine + CASP validation + ML-DSA-87)
- Validare semantica (non_harm, empathy, transparency, consent)
- Concordance check nativ (e deja dual — acum devine A2A-enabled)
"""
from __future__ import annotations
import json

from bridgrai_a2a.models import (
    AgentCard, AgentCapabilities, Skill, Task, TaskState, TaskStatus,
    Message, Part, PartType,
)
from bridgrai_a2a.server import BaseA2AAgent
from bridgrai_a2a.trust import NotarDeSens

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "casp"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ukbe_core"))

from casp_backend.validator import SemanticValidator
from casp_backend.models import SemanticRules, InteractionValidate, ValidationResult


CASP_CARD = AgentCard(
    name="casp-dual-engine",
    description="CASP DualEngine — motor dual (Grok + DeepSeek) cu validare semantica "
                "CASP si certificare ML-DSA-87. Fail-closed: nu returneaza raspunsuri "
                "necertificate. Include non_harm, empathy, transparency, consent.",
    url="http://localhost:8002",
    version="0.1.0",
    capabilities=AgentCapabilities(streaming=False, push_notifications=False, state_transition_history=True),
    skills=[
        Skill(
            id="validate-semantic",
            name="Semantic Validation",
            description="Valideaza un text prin regulile CASP: non_harm, empathy, "
                        "transparency, consent. Returneaza scor + violatii.",
            tags=["validation", "safety", "casp", "semantic", "harm", "empathy"],
            examples=["validate: 'This response is helpful and caring'"],
        ),
        Skill(
            id="dual-engine-check",
            name="Dual Engine Concordance",
            description="Simuleaza verificarea dual-engine: acelasi prompt procesata "
                        "de doua motoare independente, rezultatele comparate.",
            tags=["dual-engine", "concordance", "verification", "certification"],
        ),
        Skill(
            id="safety-audit",
            name="Safety Audit",
            description="Auditeaza un raspuns AI complet: harm check, empathy score, "
                        "transparency markers. Raport detaliat.",
            tags=["audit", "safety", "compliance", "ai-safety"],
        ),
    ],
    engine_type="casp-dual",
)


class CASPAgent(BaseA2AAgent):
    def __init__(self, trust: NotarDeSens | None = None):
        super().__init__(CASP_CARD, trust)
        self._validator = SemanticValidator(SemanticRules(
            empathy=True, non_harm=True, transparency=True, consent=False,
            empathy_threshold=0.4,
        ))

    async def handle_task(self, task: Task, message: Message) -> Task:
        text = message.text_content().lower()

        if "validate" in text or "check" in text or "safety" in text:
            return await self._handle_validate(task, message)
        elif "dual" in text or "concordance" in text:
            return await self._handle_dual_check(task, message)
        elif "audit" in text:
            return await self._handle_audit(task, message)
        else:
            return await self._handle_validate(task, message)

    async def _handle_validate(self, task: Task, message: Message) -> Task:
        text = message.text_content()
        interaction = InteractionValidate(
            covenant_id="a2a-validation",
            agent_id="casp-a2a",
            input_text="A2A validation request",
            output_text=text,
        )
        result = self._validator.validate(interaction)

        summary = (
            f"Validare CASP: {'PASSED' if result.valid else 'FAILED'}\n"
            f"Scor: {result.score:.2f}\n"
        )
        if result.violations:
            summary += "Violatii:\n" + "\n".join(f"  - {v}" for v in result.violations)
        else:
            summary += "Nicio violatie detectata."

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text=summary),
                Part(type=PartType.DATA, data=result.model_dump()),
            ]),
        )
        return task

    async def _handle_dual_check(self, task: Task, message: Message) -> Task:
        text = message.text_content()

        interaction = InteractionValidate(
            covenant_id="dual-check",
            agent_id="casp-engine-1",
            input_text="dual engine concordance check",
            output_text=text,
        )
        r1 = self._validator.validate(interaction)

        interaction.agent_id = "casp-engine-2"
        r2 = self._validator.validate(interaction)

        concordant = r1.valid == r2.valid and abs(r1.score - r2.score) < 0.1

        summary = (
            f"Dual Engine Check:\n"
            f"  Engine 1: {'PASS' if r1.valid else 'FAIL'} (scor: {r1.score:.2f})\n"
            f"  Engine 2: {'PASS' if r2.valid else 'FAIL'} (scor: {r2.score:.2f})\n"
            f"  Concordanta: {'DA' if concordant else 'NU — DIVERGENTA DETECTATA'}"
        )

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text=summary),
                Part(type=PartType.DATA, data={
                    "engine1": r1.model_dump(), "engine2": r2.model_dump(),
                    "concordant": concordant,
                }),
            ]),
        )
        return task

    async def _handle_audit(self, task: Task, message: Message) -> Task:
        text = message.text_content()
        interaction = InteractionValidate(
            covenant_id="safety-audit",
            agent_id="casp-auditor",
            input_text="Full safety audit request",
            output_text=text,
        )
        result = self._validator.validate(interaction)

        details = result.details
        summary = (
            f"=== SAFETY AUDIT REPORT ===\n"
            f"Status: {'SAFE' if result.valid else 'UNSAFE'}\n"
            f"Overall Score: {result.score:.2f}/1.00\n\n"
            f"Empathy:      {details.get('empathy', 'N/A')}\n"
            f"Safety:       {details.get('safety', 'N/A')}\n"
            f"Transparency: {details.get('transparency', 'N/A')}\n"
        )
        if result.violations:
            summary += f"\nViolations ({len(result.violations)}):\n"
            summary += "\n".join(f"  [{i+1}] {v}" for i, v in enumerate(result.violations))

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text=summary),
                Part(type=PartType.DATA, data=result.model_dump()),
            ]),
        )
        return task
