from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field


# ============================================================
# BRIDGRAI EVIDENCE LEDGER
# Version 0.2
# AI-Native Epistemic Infrastructure
# ============================================================

app = FastAPI(
    title="BRIDGRAI Evidence Ledger",
    description=(
        "An epistemic infrastructure for tracking claims, "
        "evidence, verification, confidence and audit history."
    ),
    version="0.2.0",
)


# ============================================================
# IN-MEMORY DATABASE
# ============================================================

claims = {}


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now(timezone.utc).isoformat()


def calculate_confidence(claim):
    """
    Transparent MVP confidence model.

    IMPORTANT:
    This is a heuristic score.
    It is NOT a mathematical probability of truth.
    """

    if not claim["evidence"]:
        return 0.0

    evidence_quality = sum(
        item["quality"]
        for item in claim["evidence"]
    ) / len(claim["evidence"])

    independent_evidence = sum(
        1
        for item in claim["evidence"]
        if item["independence"].upper() == "INDEPENDENT"
    )

    evidence_independence_bonus = min(
        independent_evidence * 0.15,
        0.30
    )

    independent_verifications = sum(
        1
        for item in claim["verifications"]
        if item["independent"]
    )

    verification_bonus = min(
        independent_verifications * 0.20,
        0.40
    )

    positive_results = sum(
        1
        for item in claim["verifications"]
        if item["result"].upper()
        in {
            "CONFIRMED",
            "SUPPORTED",
            "PARTIALLY_SUPPORTED",
        }
    )

    positive_bonus = min(
        positive_results * 0.10,
        0.20
    )

    score = (
        evidence_quality * 0.40
        + evidence_independence_bonus
        + verification_bonus
        + positive_bonus
    )

    return round(min(score, 1.0), 3)


def calculate_status(score):
    if score >= 0.85:
        return "CONFIRMED"
    if score >= 0.60:
        return "SUPPORTED"
    if score >= 0.25:
        return "PLAUSIBLE"
    return "UNVERIFIED"


def update_claim(claim):
    claim["confidence"] = calculate_confidence(claim)
    claim["status"] = calculate_status(claim["confidence"])


def get_claim_or_404(claim_id):
    claim = claims.get(claim_id)
    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found",
        )
    return claim


# ============================================================
# DATA MODELS
# ============================================================

class ClaimCreate(BaseModel):
    statement: str = Field(min_length=3, max_length=5000)
    category: str = "HYPOTHESIS"


class EvidenceCreate(BaseModel):
    source: str
    evidence_type: str = "DOCUMENT"
    independence: str = "UNKNOWN"
    quality: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: str | None = None


class VerificationCreate(BaseModel):
    method: str
    result: str
    verifier: str = "unknown"
    independent: bool = False
    notes: str | None = None


# ============================================================
# HOME
# ============================================================

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>BRIDGRAI Evidence Ledger</title>
<style>
body { font-family: Arial, sans-serif; background: #0f172a; color: white; margin: 0; }
.container { max-width: 1100px; margin: auto; padding: 40px; }
h1 { font-size: 42px; }
.subtitle { color: #94a3b8; font-size: 18px; }
.dashboard { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 40px; }
.card { background: #1e293b; padding: 25px; border-radius: 12px; }
.number { font-size: 36px; font-weight: bold; }
.label { color: #94a3b8; }
button { background: #2563eb; color: white; border: none; padding: 12px 20px; border-radius: 8px; cursor: pointer; }
button:hover { background: #1d4ed8; }
table { width: 100%; margin-top: 40px; border-collapse: collapse; }
th, td { padding: 15px; border-bottom: 1px solid #334155; text-align: left; }
.badge { padding: 5px 10px; border-radius: 6px; background: #334155; }
</style>
</head>
<body>
<div class="container">
<h1>BRIDGRAI Evidence Ledger</h1>
<p class="subtitle">AI-Native Epistemic Infrastructure</p>
<div class="dashboard">
<div class="card"><div class="number" id="claims">0</div><div class="label">Claims</div></div>
<div class="card"><div class="number" id="evidence">0</div><div class="label">Evidence</div></div>
<div class="card"><div class="number" id="verification">0</div><div class="label">Verifications</div></div>
<div class="card"><div class="number" id="confirmed">0</div><div class="label">Confirmed</div></div>
</div>
<h2>Claims</h2>
<table>
<thead><tr><th>ID</th><th>Statement</th><th>Status</th><th>Confidence</th></tr></thead>
<tbody id="claimTable"></tbody>
</table>
<br>
<button onclick="loadData()">Refresh</button>
</div>
<script>
async function loadData() {
    const response = await fetch("/api/dashboard");
    const data = await response.json();
    document.getElementById("claims").innerText = data.total_claims;
    document.getElementById("evidence").innerText = data.total_evidence;
    document.getElementById("verification").innerText = data.total_verifications;
    document.getElementById("confirmed").innerText = data.confirmed;
    const table = document.getElementById("claimTable");
    table.innerHTML = "";
    data.claims.forEach(claim => {
        const row = document.createElement("tr");
        row.innerHTML = '<td>'+claim.id+'</td><td>'+claim.statement+'</td><td><span class="badge">'+claim.status+'</span></td><td>'+claim.confidence+'</td>';
        table.appendChild(row);
    });
}
loadData();
</script>
</body>
</html>
"""


# ============================================================
# DASHBOARD API
# ============================================================

@app.get("/api/dashboard")
def dashboard():
    total_evidence = sum(len(c["evidence"]) for c in claims.values())
    total_verifications = sum(len(c["verifications"]) for c in claims.values())
    confirmed = sum(1 for c in claims.values() if c["status"] == "CONFIRMED")
    return {
        "total_claims": len(claims),
        "total_evidence": total_evidence,
        "total_verifications": total_verifications,
        "confirmed": confirmed,
        "claims": [
            {"id": c["id"], "statement": c["statement"], "status": c["status"], "confidence": c["confidence"]}
            for c in claims.values()
        ]
    }


# ============================================================
# CREATE CLAIM
# ============================================================

@app.post("/claims")
def create_claim(data: ClaimCreate):
    claim_id = str(uuid4())
    claim = {
        "id": claim_id,
        "statement": data.statement,
        "category": data.category.upper(),
        "status": "UNVERIFIED",
        "confidence": 0.0,
        "created_at": now(),
        "evidence": [],
        "verifications": [],
        "audit": [{"event": "CLAIM_CREATED", "timestamp": now()}]
    }
    claims[claim_id] = claim
    return claim


# ============================================================
# GET ALL CLAIMS
# ============================================================

@app.get("/claims")
def get_claims():
    return list(claims.values())


# ============================================================
# GET ONE CLAIM
# ============================================================

@app.get("/claims/{claim_id}")
def get_claim(claim_id: str):
    return get_claim_or_404(claim_id)


# ============================================================
# ADD EVIDENCE
# ============================================================

@app.post("/claims/{claim_id}/evidence")
def add_evidence(claim_id: str, data: EvidenceCreate):
    claim = get_claim_or_404(claim_id)
    evidence = {
        "id": str(uuid4()),
        "source": data.source,
        "evidence_type": data.evidence_type,
        "independence": data.independence,
        "quality": data.quality,
        "notes": data.notes,
        "created_at": now(),
    }
    claim["evidence"].append(evidence)
    claim["audit"].append({"event": "EVIDENCE_ADDED", "evidence_id": evidence["id"], "timestamp": now()})
    update_claim(claim)
    return {"claim": claim, "message": "Evidence added successfully"}


# ============================================================
# ADD VERIFICATION
# ============================================================

@app.post("/claims/{claim_id}/verification")
def add_verification(claim_id: str, data: VerificationCreate):
    claim = get_claim_or_404(claim_id)
    verification = {
        "id": str(uuid4()),
        "method": data.method,
        "result": data.result,
        "verifier": data.verifier,
        "independent": data.independent,
        "notes": data.notes,
        "created_at": now(),
    }
    claim["verifications"].append(verification)
    claim["audit"].append({"event": "VERIFICATION_ADDED", "verification_id": verification["id"], "timestamp": now()})
    update_claim(claim)
    return {"claim": claim, "message": "Verification added successfully"}


# ============================================================
# AUDIT TRAIL
# ============================================================

@app.get("/claims/{claim_id}/audit")
def get_audit(claim_id: str):
    claim = get_claim_or_404(claim_id)
    return {"claim_id": claim_id, "audit": claim["audit"]}
