"""
HASN — A2A Agent Wrapper.

Expune HASN (Hybrid Autonomous Security Network) ca agent A2A.
HASN e Node.js — acest wrapper comunica cu el prin HTTP (API bridge).
Daca HASN nu ruleaza, returneaza stare simulata pentru demo.

Skill-uri:
- Security status (stats real-time)
- Threat assessment (analiza IP/request)
- Audit query (interogare jurnal de audit)
"""
from __future__ import annotations
import json

import httpx

from bridgrai_a2a.models import (
    AgentCard, AgentCapabilities, Skill, Task, TaskState, TaskStatus,
    Message, Part, PartType,
)
from bridgrai_a2a.server import BaseA2AAgent
from bridgrai_a2a.trust import NotarDeSens


HASN_CARD = AgentCard(
    name="hasn-security",
    description="HASN — Hybrid Autonomous Security Network. Monitorizare securitate "
                "in timp real: violation detection, auto-blocking, geolocation, audit log. "
                "Bridge A2A catre backend-ul Node.js.",
    url="http://localhost:8003",
    version="0.1.0",
    capabilities=AgentCapabilities(streaming=False, push_notifications=True, state_transition_history=True),
    skills=[
        Skill(
            id="security-status",
            name="Security Status",
            description="Returneaza statusul de securitate in timp real: "
                        "violatii recente, IP-uri active, nivel de amenintare.",
            tags=["security", "status", "monitoring", "real-time"],
            examples=["what is the current security status?"],
        ),
        Skill(
            id="threat-assess",
            name="Threat Assessment",
            description="Evalueaza nivelul de amenintare al unui IP sau request. "
                        "Include geolocation si scor de risc.",
            tags=["threat", "assessment", "ip", "risk", "geolocation"],
            examples=["assess threat level for IP 192.168.1.1"],
        ),
        Skill(
            id="security-report",
            name="Security Report",
            description="Genereaza raport de securitate: violatii pe severitate, "
                        "IP-uri unice, tendinte pe ultimele 24h.",
            tags=["report", "audit", "violations", "security"],
        ),
    ],
    engine_type="hasn-node",
)

HASN_BACKEND = "http://localhost:3001"


class HASNAgent(BaseA2AAgent):
    def __init__(self, trust: NotarDeSens | None = None):
        super().__init__(HASN_CARD, trust)
        self._http = httpx.AsyncClient(timeout=10.0)

    async def _hasn_available(self) -> bool:
        try:
            resp = await self._http.get(f"{HASN_BACKEND}/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def handle_task(self, task: Task, message: Message) -> Task:
        text = message.text_content().lower()

        if "status" in text or "monitor" in text:
            return await self._handle_status(task)
        elif "threat" in text or "assess" in text or "ip" in text:
            return await self._handle_threat(task, message)
        elif "report" in text or "audit" in text:
            return await self._handle_report(task)
        else:
            return await self._handle_status(task)

    async def _handle_status(self, task: Task) -> Task:
        if await self._hasn_available():
            resp = await self._http.get(f"{HASN_BACKEND}/api/security/stats")
            data = resp.json()
            rt = data.get("realTime", {})
            summary = (
                f"HASN Security Status (live):\n"
                f"  Violatii recente (5min): {rt.get('recent_violations', 0)}\n"
                f"  Critical: {rt.get('recent_critical', 0)}\n"
                f"  IP-uri active: {rt.get('active_ips', 0)}\n"
                f"  Status: {'ALERT' if int(rt.get('recent_critical', 0)) > 0 else 'NORMAL'}"
            )
            task.status = TaskStatus(
                state=TaskState.COMPLETED,
                message=Message(role="agent", parts=[
                    Part(type=PartType.TEXT, text=summary),
                    Part(type=PartType.DATA, data=data),
                ]),
            )
        else:
            task.status = TaskStatus(
                state=TaskState.COMPLETED,
                message=Message(role="agent", parts=[
                    Part(type=PartType.TEXT, text=(
                        "HASN Backend offline (Node.js pe port 3001 nu raspunde).\n"
                        "Status simulat: NORMAL — 0 violatii, 0 amenintari.\n"
                        "Porneste HASN: cd repos/hasn && node server-complete.js"
                    )),
                    Part(type=PartType.DATA, data={"live": False, "simulated": True}),
                ]),
            )
        return task

    async def _handle_threat(self, task: Task, message: Message) -> Task:
        text = message.text_content()
        import re
        ip_match = re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", text)
        ip = ip_match.group() if ip_match else "unknown"

        summary = (
            f"Threat Assessment for {ip}:\n"
            f"  Geolocation: requires MaxMind DB\n"
            f"  Risk score: requires live HASN backend\n"
            f"  Recommendation: {'CHECK HASN BACKEND' if not await self._hasn_available() else 'LIVE ASSESSMENT AVAILABLE'}"
        )
        task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[
                Part(type=PartType.TEXT, text=summary),
            ]),
        )
        return task

    async def _handle_report(self, task: Task) -> Task:
        if await self._hasn_available():
            resp = await self._http.get(f"{HASN_BACKEND}/api/security/report", params={"timeRange": "24h"})
            data = resp.json()
            s = data.get("summary", {})
            summary = (
                f"HASN Security Report (24h):\n"
                f"  Total violatii: {s.get('total', 0)}\n"
                f"  Critical: {s.get('critical', 0)}\n"
                f"  High: {s.get('high', 0)}\n"
                f"  Medium: {s.get('medium', 0)}\n"
                f"  Low: {s.get('low', 0)}\n"
                f"  Resolved: {s.get('resolved', 0)}\n"
                f"  IP-uri unice: {s.get('unique_ips', 0)}"
            )
            task.status = TaskStatus(
                state=TaskState.COMPLETED,
                message=Message(role="agent", parts=[
                    Part(type=PartType.TEXT, text=summary),
                    Part(type=PartType.DATA, data=data.get("summary", {})),
                ]),
            )
        else:
            task.status = TaskStatus(
                state=TaskState.COMPLETED,
                message=Message(role="agent", parts=[
                    Part(type=PartType.TEXT, text="HASN Backend offline — nu pot genera raport live."),
                ]),
            )
        return task
