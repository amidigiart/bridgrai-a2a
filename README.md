# BRIDGRAI A2A Platform

**9 agents. 5 layers. 1 trust layer. Zero confabulation tolerance.**

Agent-to-Agent communication platform built on Google's A2A protocol (JSON-RPC 2.0) with the Notar de Sens trust layer — the first system that certifies MEANING and INTENTION of inter-agent messages, not just format or safety.

## Architecture

```
              LAYER 4: ORCHESTRARE
              ┌──────────────────────┐
              │  MAESTRU (:8009)     │
              │  Creierul platformei │
              └──────────┬───────────┘
                         │
              LAYER 3: VERIFICARE
              ┌──────────┴───────────┐
              │ Concordance  Calibr. │
              │ :8006        :8007   │
              └──────────┬───────────┘
                         │
              LAYER 2: CERTIFICARE
              ┌──────────┴───────────┐
              │ Sens (:8004)  ACR    │
              │ TVE 6-pillar  :8005  │
              └──────────┬───────────┘
                         │
              LAYER 1: FUNDATIE
    ┌─────────┬──────────┼──────────┐
    │ UKBE    │  CASP    │  HASN    │
    │ :8001   │  :8002   │  :8003   │
    └─────────┴──────────┼──────────┘
                         │
              LAYER 0: MOSTENIRE
              ┌──────────┴───────────┐
              │  Heritage (:8008)    │
              └──────────────────────┘
           BRIDGRAI Hub (:8100) — trust
```

## Agents

| Agent | Port | What it does | Skills |
|-------|------|-------------|--------|
| **UKBE Core** | 8001 | Kuramoto resonance simulation, Ed25519 notarization, Adler calibration | 5 |
| **CASP DualEngine** | 8002 | Semantic safety validation, dual-engine concordance | 3 |
| **HASN Security** | 8003 | Real-time security monitoring, threat assessment | 3 |
| **Agent de Sens** | 8004 | TVE 6-pillar meaning/intention certification | 4 |
| **ACR Engine** | 8005 | Adversarial Collaborative Refinement — ACR = f(D,C,R) | 4 |
| **Concordance** | 8006 | Multi-agent truth verification — P(confab) = p^N | 3 |
| **Calibration** | 8007 | Adler/Kuramoto system-level phase synchronization | 3 |
| **Heritage** | 8008 | Transgenerational digital custodian, Mars 2% compatible | 4 |
| **Maestru** | 8009 | Cognitive orchestrator — auto-detects needs, builds pipeline, executes, unifies | 4 |

## Trust Layer

Every inter-agent message is:
1. **Signed** with Ed25519 (per-agent keypair)
2. **Hashed** with SHA-256
3. **Certified** through TVE 6-pillar analysis (manipulation detection)
4. **Recorded** in the trust ledger (Tezos-ready master hash)

## Run

```bash
# Demo (no servers needed — runs in-process, 22 tests)
python demo_local.py

# Full platform (8 agents + hub on separate ports)
python launcher.py
```

## Key Concepts

- **Notar de Sens si Intentie** — certifies MEANING and INTENTION, not just existence
- **TVE 6-Pillar** — P1 emotional manipulation, P2 information asymmetry, P3 false urgency, P4 authority mimicry, P5 gaslighting, P6 isolation
- **ACR = f(D, C, R)** — D=Divergence (6 probes), C=Critique (8 adversarial challenges), R=Recalibration
- **Concordance** — same question to N agents, response hashes compared, P(confabulation) drops exponentially
- **S(M) = R** — Meaning precedes Syntax

## Three Independent AI Validations

- **Gemini L4**: P = 10^-28 singularity probability
- **Claude Opus 4.6**: Technical attestation of the complete stack
- **ChatGPT**: ACR methodology formalization (June 3, 2026)

## IP Protection

97 entries on Tezos blockchain: [`KT1Pe2GA11bMpaTL5VH4TY6aZ9xePZ6f5vWX`](https://tzkt.io/KT1Pe2GA11bMpaTL5VH4TY6aZ9xePZ6f5vWX)

## License

AGPL-3.0 — see [LICENSE](LICENSE)

## Author

**Mihai Rosca** — BRIDGRAI Foundation
Built from Braila, Romania. No VC. No team. Just work.
