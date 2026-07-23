"""
BRIDGRAI Hub — Discovery + Routing + Trust Orchestration.

Hub-ul central prin care agentii se gasesc, comunica, si sunt verificati.
- Registry: agenti inregistrati cu Agent Card
- Router: trimite taskuri catre agentul potrivit pe baza de skill matching
- Trust: fiecare tranzactie trece prin Notar de Sens
- Ledger: log complet, hash-abil, Tezos-ready
"""
from __future__ import annotations
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    AgentCard, Message, Part, PartType, Task, TaskState, TaskStatus, Skill,
    jsonrpc_request, jsonrpc_response, jsonrpc_error,
)
from .trust import NotarDeSens, AgentIdentity
from .client import A2AClient

logger = logging.getLogger("bridgrai.hub")


@dataclass
class RegisteredAgent:
    card: AgentCard
    base_url: str
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    healthy: bool = True


class BRIDGRAIHub:
    """Hub-ul central al ecosistemului BRIDGRAI A2A.

    Responsabilitati:
    1. Registry — tine evidenta tuturor agentilor
    2. Discovery — expune lista de agenti si skill-uri
    3. Routing — directioneaza taskuri catre agentul potrivit
    4. Trust — verifica fiecare tranzactie prin Notar de Sens
    5. Concordance — verifica raspunsuri multiple la aceeasi intrebare
    6. Ledger — log complet Tezos-ready
    """

    def __init__(self):
        self.trust = NotarDeSens()
        self.identity = AgentIdentity.generate("bridgrai-hub")
        self.trust.register_agent(self.identity)
        self._agents: dict[str, RegisteredAgent] = {}
        self._client = A2AClient(trust=self.trust, identity=self.identity)
        self._transaction_log: list[dict] = []

    def register_agent(self, card: AgentCard, base_url: str) -> RegisteredAgent:
        agent = RegisteredAgent(card=card, base_url=base_url)
        self._agents[card.name] = agent
        logger.info("Agent registered: %s at %s", card.name, base_url)
        return agent

    def find_agent_by_skill(self, query: str) -> list[RegisteredAgent]:
        results = []
        query_lower = query.lower()
        for agent in self._agents.values():
            for skill in agent.card.skills:
                if (query_lower in skill.name.lower() or
                    query_lower in skill.description.lower() or
                    any(query_lower in t.lower() for t in skill.tags)):
                    results.append(agent)
                    break
        return results

    async def route_task(self, message: Message, target_agent: str | None = None) -> dict:
        """Trimite un task catre un agent specific sau catre cel mai potrivit."""
        if target_agent:
            agent = self._agents.get(target_agent)
            if not agent:
                return {"error": f"Agent not found: {target_agent}"}
            return await self._send_to_agent(agent, message)

        text = message.text_content().lower()
        best = self._match_agent(text)
        if not best:
            return {"error": "No matching agent found", "query": text}
        return await self._send_to_agent(best, message)

    async def concordance_check(self, message: Message, agent_names: list[str] | None = None) -> dict:
        """Trimite aceeasi intrebare la mai multi agenti si verifica concordanta."""
        targets = agent_names or list(self._agents.keys())
        urls = []
        for name in targets:
            agent = self._agents.get(name)
            if agent:
                urls.append(agent.base_url)

        return await self._client.send_to_multiple(urls, message)

    def _match_agent(self, query: str) -> RegisteredAgent | None:
        scores: list[tuple[int, RegisteredAgent]] = []
        for agent in self._agents.values():
            if not agent.healthy:
                continue
            score = 0
            for skill in agent.card.skills:
                for tag in skill.tags:
                    if tag.lower() in query:
                        score += 2
                if any(w in skill.description.lower() for w in query.split()):
                    score += 1
            if score > 0:
                scores.append((score, agent))
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1] if scores else None

    async def _send_to_agent(self, agent: RegisteredAgent, message: Message) -> dict:
        ts = datetime.now(timezone.utc).isoformat()
        try:
            result = await self._client.send_task(agent.base_url, message)
            self._transaction_log.append({
                "timestamp": ts, "target": agent.card.name,
                "status": "success", "task": result.get("result", {}).get("id"),
            })
            return result
        except Exception as e:
            self._transaction_log.append({
                "timestamp": ts, "target": agent.card.name,
                "status": "error", "error": str(e),
            })
            return {"error": str(e), "agent": agent.card.name}

    def create_app(self) -> FastAPI:
        app = FastAPI(title="BRIDGRAI Hub", version="0.1.0",
                      description="A2A Discovery + Routing + Trust Hub")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
        )

        @app.get("/.well-known/agent.json")
        async def hub_card():
            return AgentCard(
                name="bridgrai-hub",
                description="BRIDGRAI A2A Hub — discovery, routing, trust orchestration",
                url="http://localhost:8100",
                skills=[
                    Skill(id="discovery", name="Agent Discovery", description="Find agents by capability", tags=["discovery", "registry"]),
                    Skill(id="routing", name="Task Routing", description="Route tasks to the right agent", tags=["routing"]),
                    Skill(id="concordance", name="Concordance Check", description="Verify multi-agent agreement", tags=["trust", "concordance"]),
                ],
                engine_type="hub",
            ).to_dict()

        @app.get("/agents")
        async def list_agents():
            return {
                "agents": [
                    {
                        "name": a.card.name,
                        "description": a.card.description,
                        "url": a.base_url,
                        "skills": [s.to_dict() for s in a.card.skills],
                        "healthy": a.healthy,
                        "registeredAt": a.registered_at,
                    }
                    for a in self._agents.values()
                ]
            }

        @app.post("/agents/register")
        async def register_agent(request: Request):
            body = await request.json()
            card = AgentCard(
                name=body["name"],
                description=body.get("description", ""),
                url=body["url"],
                skills=[Skill(**s) for s in body.get("skills", [])],
                engine_type=body.get("engineType"),
            )
            agent = self.register_agent(card, body["url"])
            return {"registered": True, "agent": agent.card.name}

        @app.get("/agents/search")
        async def search_agents(q: str = ""):
            matches = self.find_agent_by_skill(q)
            return {"query": q, "results": [
                {"name": a.card.name, "description": a.card.description, "url": a.base_url}
                for a in matches
            ]}

        @app.post("/route")
        async def route_task(request: Request):
            body = await request.json()
            parts = [Part(type=PartType.TEXT, text=body.get("message", ""))]
            message = Message(role="user", parts=parts)
            target = body.get("target")
            return await self.route_task(message, target)

        @app.post("/concordance")
        async def concordance(request: Request):
            body = await request.json()
            parts = [Part(type=PartType.TEXT, text=body.get("message", ""))]
            message = Message(role="user", parts=parts)
            agents = body.get("agents")
            return await self.concordance_check(message, agents)

        @app.get("/trust/ledger")
        async def trust_ledger():
            return {
                "ledger": self.trust.get_ledger(),
                "masterHash": self.trust.master_hash(),
                "transactions": len(self._transaction_log),
            }

        @app.get("/health")
        async def health():
            return {
                "hub": "bridgrai-a2a",
                "status": "ok",
                "agents": len(self._agents),
                "transactions": len(self._transaction_log),
                "trustRecords": len(self.trust._ledger),
                "hubPublicKey": self.identity.public_key_hex()[:16] + "...",
            }

        return app
