"""
FastAPI app instances — importate de uvicorn prin launcher.py.

Fiecare agent primeste un trust engine comun (NotarDeSens),
asa ca fiecare mesaj inter-agent e verificabil.
"""
from .trust import NotarDeSens
from .hub import BRIDGRAIHub

import sys, os
_repos = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(_repos, "ukbe_core"))
sys.path.insert(0, os.path.join(_repos, "casp"))

trust = NotarDeSens()

hub_instance = BRIDGRAIHub()
hub_app = hub_instance.create_app()

from agents.ukbe_a2a import UKBEAgent  # noqa: E402
ukbe_agent = UKBEAgent(trust=trust)
ukbe_app = ukbe_agent.create_app()

from agents.casp_a2a import CASPAgent  # noqa: E402
casp_agent = CASPAgent(trust=trust)
casp_app = casp_agent.create_app()

from agents.hasn_a2a import HASNAgent  # noqa: E402
hasn_agent = HASNAgent(trust=trust)
hasn_app = hasn_agent.create_app()

from agents.sens_a2a import AgentDeSens  # noqa: E402
sens_agent = AgentDeSens(trust=trust)
sens_app = sens_agent.create_app()

from agents.acr_a2a import ACRAgent  # noqa: E402
acr_agent = ACRAgent(trust=trust)
acr_app = acr_agent.create_app()

from agents.concordance_a2a import ConcordanceAgent  # noqa: E402
concordance_agent = ConcordanceAgent(trust=trust)
concordance_app = concordance_agent.create_app()

from agents.calibration_a2a import CalibrationAgent  # noqa: E402
calibration_agent = CalibrationAgent(trust=trust)
calibration_app = calibration_agent.create_app()

from agents.heritage_a2a import HeritageAgent  # noqa: E402
heritage_agent = HeritageAgent(trust=trust)
heritage_app = heritage_agent.create_app()

from agents.quantum_a2a import QuantumAgent  # noqa: E402
quantum_agent = QuantumAgent()
quantum_app = quantum_agent.create_app()

from agents.maestru_a2a import MaestruAgent  # noqa: E402
maestru_agent = MaestruAgent(
    trust=trust,
    agents={
        "agent-de-sens": sens_agent,
        "acr-engine": acr_agent,
        "agent-concordance": concordance_agent,
        "agent-calibration": calibration_agent,
        "agent-heritage": heritage_agent,
        "ukbe-core": ukbe_agent,
        "casp-dual-engine": casp_agent,
        "hasn-security": hasn_agent,
        "agent-quantum": quantum_agent,
    },
)
maestru_app = maestru_agent.create_app()
