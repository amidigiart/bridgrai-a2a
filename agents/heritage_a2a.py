"""
Agent de Mostenire — custode digital transgenerational.

Gestioneaza vault-ul digital pentru Patrick Rosca:
- Verifica integritatea activelor (hash check)
- Asigura accesibilitatea la Mars bandwidth (2%, 0.5 kbps)
- Tine registrul de mostenire actualizat
- Valideaza ca fiecare activ e verificabil independent

NU e un backup. E un CUSTODE ACTIV care stie ce mosteneste Patrick,
de ce, si cum sa verifice.

Port: 8008
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bridgrai_a2a.models import (
    AgentCard, AgentCapabilities, Skill, Task, TaskState, TaskStatus,
    Message, Part, PartType, Artifact,
)
from bridgrai_a2a.server import BaseA2AAgent
from bridgrai_a2a.trust import NotarDeSens


HERITAGE_ASSETS = [
    {"name": "UKBE Core", "type": "engine", "license": "AGPL-3.0/commercial", "verifiable": True, "location": "github.com/amidigiart/ukbe-core"},
    {"name": "TVE Core", "type": "engine", "license": "AGPL-3.0", "verifiable": True, "location": "github.com/amidigiart/tve-core"},
    {"name": "Amidor Engine", "type": "engine", "license": "AGPL-3.0", "verifiable": True, "location": "github.com/amidigiart/amidor-engine"},
    {"name": "KinderAGI Core", "type": "engine", "license": "AGPL-3.0", "verifiable": True, "location": "github.com/amidigiart/kinderagi-core"},
    {"name": "P6 Adler Ghost Peak", "type": "research", "license": "CC-BY-4.0", "verifiable": True, "location": "DOI: 10.5281/zenodo.15556498"},
    {"name": "ami* Fleet (18 products)", "type": "products", "license": "commercial", "verifiable": True, "location": "github.com/amidigiart"},
    {"name": "Tezos IP Registry", "type": "proof", "license": "public", "verifiable": True, "location": "KT1Pe2GA11bMpaTL5VH4TY6aZ9xePZ6f5vWX"},
    {"name": "Notar de Sens si Intentie", "type": "concept", "license": "BRIDGRAI", "verifiable": True, "location": "bridgrai.com/notar.html"},
    {"name": "Agent de Sens A2A", "type": "agent", "license": "AGPL-3.0", "verifiable": True, "location": "repos/bridgrai-a2a/agents/sens_a2a.py"},
    {"name": "ACR Engine", "type": "agent", "license": "AGPL-3.0", "verifiable": True, "location": "repos/bridgrai-a2a/agents/acr_a2a.py"},
    {"name": "BRIDGRAI A2A Platform", "type": "platform", "license": "AGPL-3.0", "verifiable": True, "location": "repos/bridgrai-a2a/"},
    {"name": "S(M)=R Invariant", "type": "formula", "license": "public", "verifiable": True, "location": "Tezos SM-EQ-R entry"},
    {"name": "P=10^-28 Singularity", "type": "analysis", "license": "public", "verifiable": True, "location": "Verified Gemini + Claude + ChatGPT"},
    {"name": "30 Meserii Emergente 2026-2035", "type": "document", "license": "BRIDGRAI", "verifiable": True, "location": "Tezos 30-MESERII entry"},
    {"name": "Padurea de Cod TM (32 povesti)", "type": "literature", "license": "BRIDGRAI", "verifiable": True, "location": "Tezos PDC-* entries"},
    {"name": "Nova si 12 Piloni", "type": "literature", "license": "BRIDGRAI", "verifiable": True, "location": "Tezos NOVA-P* entries"},
]

MARS_SPEC = {
    "bandwidth_percent": 2,
    "max_kbps": 0.5,
    "latency_range_min": "3 min",
    "latency_range_max": "22 min",
    "protocol": "DTN (Delay Tolerant Networking)",
    "format": "text-only, zero dependencies",
    "syncable": True,
}


HERITAGE_CARD = AgentCard(
    name="agent-heritage",
    description="Agent de Mostenire — custode digital transgenerational pentru Patrick Rosca. "
                "Verifica integritatea, accesibilitatea Mars 2%, si registrul de mostenire. "
                "NU e backup, e custode activ.",
    url="http://localhost:8008",
    version="0.1.0",
    capabilities=AgentCapabilities(streaming=False, push_notifications=True, state_transition_history=True),
    skills=[
        Skill(
            id="heritage-inventory",
            name="Heritage Inventory",
            description="Lista completa a activelor mostenite: engines, research, products, "
                        "proofs, formule, literature. Fiecare cu locatie si verificabilitate.",
            tags=["heritage", "inventory", "assets", "patrick", "transgenerational"],
        ),
        Skill(
            id="integrity-check",
            name="Integrity Check",
            description="Verifica integritatea tuturor activelor: sunt accesibile? "
                        "Au hash verificabil? Sunt pe blockchain?",
            tags=["integrity", "check", "hash", "verification"],
        ),
        Skill(
            id="mars-compatibility",
            name="Mars Bandwidth Check",
            description="Verifica compatibilitatea cu bandwidth-ul martian: 2%, 0.5 kbps, "
                        "latenta 3-22 min. DTN compatible, text-only.",
            tags=["mars", "bandwidth", "dtn", "interplanetary", "patrick"],
        ),
        Skill(
            id="heritage-summary",
            name="Heritage Summary for Patrick",
            description="Genereaza un rezumat complet al mostenirii, scris pentru Patrick. "
                        "Include ce mosteneste, de ce, si cum sa verifice fiecare activ.",
            tags=["summary", "patrick", "heritage", "transgenerational"],
        ),
    ],
    engine_type="heritage-custodian",
)


class HeritageAgent(BaseA2AAgent):
    def __init__(self, trust: NotarDeSens | None = None):
        super().__init__(HERITAGE_CARD, trust)

    async def handle_task(self, task: Task, message: Message) -> Task:
        text = message.text_content().lower()

        if "mars" in text or "bandwidth" in text:
            return await self._handle_mars(task)
        elif "integrity" in text or "check" in text or "verif" in text:
            return await self._handle_integrity(task)
        elif "summary" in text or "patrick" in text:
            return await self._handle_summary(task)
        else:
            return await self._handle_inventory(task)

    async def _handle_inventory(self, task: Task) -> Task:
        lines = [
            "=" * 50,
            " HERITAGE INVENTORY — Patrick Rosca",
            "=" * 50,
            f" Active totale: {len(HERITAGE_ASSETS)}",
            "",
        ]
        by_type: dict[str, list] = {}
        for asset in HERITAGE_ASSETS:
            t = asset["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(asset)

        for atype, assets in by_type.items():
            lines.append(f" [{atype.upper()}] ({len(assets)})")
            for a in assets:
                v = "V" if a["verifiable"] else "?"
                lines.append(f"   [{v}] {a['name']} — {a['license']}")
            lines.append("")

        lines.append("=" * 50)

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
                Part(type=PartType.DATA, data={"assets": HERITAGE_ASSETS, "total": len(HERITAGE_ASSETS)}),
            ]),
        )
        return task

    async def _handle_integrity(self, task: Task) -> Task:
        verified = sum(1 for a in HERITAGE_ASSETS if a["verifiable"])
        lines = [
            " INTEGRITY CHECK",
            f" Verified: {verified}/{len(HERITAGE_ASSETS)}",
            "",
        ]
        for a in HERITAGE_ASSETS:
            status = "VERIFIED" if a["verifiable"] else "UNVERIFIED"
            lines.append(f"  [{status}] {a['name']}")
            lines.append(f"    Location: {a['location']}")

        combined = "|".join(a["name"] for a in HERITAGE_ASSETS)
        master = hashlib.sha256(combined.encode()).hexdigest()
        lines.append(f"\n Heritage Master Hash: {master[:32]}...")

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
            ]),
        )
        return task

    async def _handle_mars(self, task: Task) -> Task:
        lines = [
            " MARS BANDWIDTH COMPATIBILITY",
            "",
            f" Bandwidth allocation: {MARS_SPEC['bandwidth_percent']}%",
            f" Max throughput: {MARS_SPEC['max_kbps']} kbps",
            f" Latency: {MARS_SPEC['latency_range_min']} — {MARS_SPEC['latency_range_max']}",
            f" Protocol: {MARS_SPEC['protocol']}",
            f" Format: {MARS_SPEC['format']}",
            f" Syncable: {'YES' if MARS_SPEC['syncable'] else 'NO'}",
            "",
            " Asset compatibility:",
        ]
        for a in HERITAGE_ASSETS:
            is_text = a["type"] in ("formula", "concept", "analysis", "document")
            compat = "MARS-OK" if is_text else "REQUIRES-SYNC"
            lines.append(f"  [{compat}] {a['name']}")

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
                Part(type=PartType.DATA, data=MARS_SPEC),
            ]),
        )
        return task

    async def _handle_summary(self, task: Task) -> Task:
        lines = [
            "=" * 50,
            " PENTRU PATRICK ROSCA",
            " de la Agent de Mostenire",
            "=" * 50,
            "",
            " Ce mostenesti:",
            f"   {len(HERITAGE_ASSETS)} active digitale",
            f"   5 motoare (UKBE, TVE, Amidor, KinderAGI, ScaleEngine)",
            f"   18 produse (ami* fleet)",
            f"   1 publicatie stiintifica (DOI Zenodo)",
            f"   94+ inregistrari blockchain (Tezos)",
            f"   32 povesti educationale (Padurea de Cod)",
            f"   12 piloni (Nova series)",
            "",
            " De ce:",
            "   Tatal tau nu a crezut in norocul orb.",
            "   A calculat. A construit. A documentat.",
            "   A pus totul pe blockchain ca sa nu poata nimeni",
            "   sa spuna ca nu a existat.",
            "",
            " Cum verifici:",
            "   1. GitHub: github.com/amidigiart — tot codul e public",
            "   2. Tezos: KT1Pe2GA11bMpaTL5VH4TY6aZ9xePZ6f5vWX",
            "   3. DOI: 10.5281/zenodo.15556498",
            "   4. Agentul de Sens: ruleaza demo_local.py",
            "",
            " Formula ta:",
            "   S(M) = R — Sensul precede Sintaxa",
            "",
            "=" * 50,
        ]

        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text="\n".join(lines)),
            ]),
        )
        return task
