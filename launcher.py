"""
BRIDGRAI A2A Launcher — porneste hub-ul + toti agentii pe porturi separate.

Porturi:
  8100 — BRIDGRAI Hub (discovery + routing + trust)
  8001 — UKBE Core (Kuramoto + notary + DID)
  8002 — CASP DualEngine (dual-engine + validare semantica)
  8003 — HASN Security (bridge catre Node.js backend)

Utilizare:
  python launcher.py              # porneste tot
  python launcher.py --hub-only   # doar hub-ul
  python launcher.py --demo       # porneste tot + ruleaza demo
"""
from __future__ import annotations
import argparse
import asyncio
import multiprocessing
import sys
import time

import uvicorn


def run_server(module_path: str, host: str, port: int):
    uvicorn.run(module_path, host=host, port=port, log_level="info")


def start_hub():
    from bridgrai_a2a.hub import BRIDGRAIHub
    hub = BRIDGRAIHub()
    app = hub.create_app()

    import importlib
    mod = importlib.import_module("bridgrai_a2a._hub_app")
    return app


def main():
    parser = argparse.ArgumentParser(description="BRIDGRAI A2A Platform Launcher")
    parser.add_argument("--hub-only", action="store_true", help="Porneste doar hub-ul")
    parser.add_argument("--demo", action="store_true", help="Ruleaza demo dupa pornire")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = parser.parse_args()

    print("=" * 60)
    print("  BRIDGRAI A2A Platform")
    print("  Notar de Sens si Intentie — Trust Layer")
    print("=" * 60)
    print()

    processes: list[multiprocessing.Process] = []

    configs = [
        ("BRIDGRAI Hub", "bridgrai_a2a._apps:hub_app", args.host, 8100),
    ]

    if not args.hub_only:
        configs.extend([
            ("UKBE Core", "bridgrai_a2a._apps:ukbe_app", args.host, 8001),
            ("CASP DualEngine", "bridgrai_a2a._apps:casp_app", args.host, 8002),
            ("HASN Security", "bridgrai_a2a._apps:hasn_app", args.host, 8003),
            ("Agent de Sens", "bridgrai_a2a._apps:sens_app", args.host, 8004),
            ("ACR Engine", "bridgrai_a2a._apps:acr_app", args.host, 8005),
            ("Concordance", "bridgrai_a2a._apps:concordance_app", args.host, 8006),
            ("Calibration", "bridgrai_a2a._apps:calibration_app", args.host, 8007),
            ("Heritage", "bridgrai_a2a._apps:heritage_app", args.host, 8008),
            ("Maestru", "bridgrai_a2a._apps:maestru_app", args.host, 8009),
        ])

    for name, module_path, host, port in configs:
        print(f"  Starting {name} on {host}:{port}...")
        p = multiprocessing.Process(target=run_server, args=(module_path, host, port))
        p.daemon = True
        p.start()
        processes.append(p)

    print()
    print("  All agents running. Endpoints:")
    print(f"    Hub:      http://{args.host}:8100")
    if not args.hub_only:
        print(f"    UKBE:     http://{args.host}:8001")
        print(f"    CASP:     http://{args.host}:8002")
        print(f"    HASN:     http://{args.host}:8003")
        print(f"    SENS:     http://{args.host}:8004")
        print(f"    ACR:      http://{args.host}:8005")
        print(f"    CONCORD:  http://{args.host}:8006")
        print(f"    CALIBR:   http://{args.host}:8007")
        print(f"    HERITAGE: http://{args.host}:8008")
        print(f"    MAESTRU:  http://{args.host}:8009")
    print()
    print("  Agent Cards:")
    print(f"    http://{args.host}:8100/.well-known/agent.json")
    if not args.hub_only:
        print(f"    http://{args.host}:8001/.well-known/agent.json")
        print(f"    http://{args.host}:8002/.well-known/agent.json")
        print(f"    http://{args.host}:8003/.well-known/agent.json")
        print(f"    http://{args.host}:8004/.well-known/agent.json")
        print(f"    http://{args.host}:8005/.well-known/agent.json")
        print(f"    http://{args.host}:8006/.well-known/agent.json")
        print(f"    http://{args.host}:8007/.well-known/agent.json")
        print(f"    http://{args.host}:8008/.well-known/agent.json")
        print(f"    http://{args.host}:8009/.well-known/agent.json")
    print()
    print("  Press Ctrl+C to stop all agents.")
    print("=" * 60)

    if args.demo:
        time.sleep(3)
        print("\n  Running demo...\n")
        asyncio.run(run_demo(args.host))

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        for p in processes:
            p.terminate()


async def run_demo(host: str):
    """Demo interactiv: agentii comunica prin hub."""
    from bridgrai_a2a.client import A2AClient
    from bridgrai_a2a.models import Message, Part, PartType

    client = A2AClient()

    print("  [1] Discovering agents...")
    for port in [8100, 8001, 8002, 8003]:
        try:
            card = await client.discover(f"http://{host}:{port}")
            print(f"      Found: {card.name} — {card.description[:60]}...")
        except Exception as e:
            print(f"      Port {port}: {e}")

    print("\n  [2] Sending Kuramoto simulation to UKBE...")
    msg = Message(role="user", parts=[Part(type=PartType.TEXT, text="simulate kuramoto 100 steps")])
    result = await client.send_task(f"http://{host}:8001", msg)
    status = result.get("result", {}).get("status", {})
    agent_msg = status.get("message", {})
    for part in agent_msg.get("parts", []):
        if part.get("text"):
            print(f"      {part['text']}")

    print("\n  [3] Sending safety validation to CASP...")
    msg = Message(role="user", parts=[Part(type=PartType.TEXT, text="validate: I understand your concern and I want to help you find a solution")])
    result = await client.send_task(f"http://{host}:8002", msg)
    status = result.get("result", {}).get("status", {})
    agent_msg = status.get("message", {})
    for part in agent_msg.get("parts", []):
        if part.get("text"):
            print(f"      {part['text']}")

    print("\n  [4] Checking HASN security status...")
    msg = Message(role="user", parts=[Part(type=PartType.TEXT, text="security status")])
    result = await client.send_task(f"http://{host}:8003", msg)
    status = result.get("result", {}).get("status", {})
    agent_msg = status.get("message", {})
    for part in agent_msg.get("parts", []):
        if part.get("text"):
            print(f"      {part['text']}")

    print("\n  [5] Cross-agent concordance check...")
    msg = Message(role="user", parts=[Part(type=PartType.TEXT, text="status snapshot")])
    for port in [8001, 8002]:
        result = await client.send_task(f"http://{host}:{port}", msg)
        name = "UKBE" if port == 8001 else "CASP"
        state = result.get("result", {}).get("status", {}).get("state", "?")
        print(f"      {name}: {state}")

    await client.close()
    print("\n  Demo complete. S(M)=R.\n")


if __name__ == "__main__":
    main()
