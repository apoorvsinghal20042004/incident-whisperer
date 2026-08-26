"""
Evaluation harness for Incident Whisperer.

Runs the full agent pipeline against known test cases and measures
root cause identification accuracy.

Usage:
    python3 -m app.evaluation.harness
"""
import asyncio
import uuid
import sys
from datetime import datetime, UTC
from typing import Optional

# Add project root to path for mock_services
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.models import incident, log_embedding
from app.agents.graph import incident_graph
from app.services.embeddings import ingest_logs
from app.db.database import AsyncSessionLocal
from mock_services.simulator import generate_incident_data, SCENARIO_REGISTRY
from mock_services.services import get_all_service_names, get_services_with_database


# --- Test cases ---
# Each test case has:
#   scenario: which failure scenario to simulate
#   service:  which service is the root cause
#   expected_root_service: what the agent should identify
TEST_CASES = [
    # Connection pool exhaustion — agent must trace from dependent to root
    {"scenario": "connection_pool_exhaustion", "service": "order-service",
     "expected_root_service": "order-service"},
    {"scenario": "connection_pool_exhaustion", "service": "auth-service",
     "expected_root_service": "auth-service"},
    {"scenario": "connection_pool_exhaustion", "service": "payment-service",
     "expected_root_service": "payment-service"},

    # Memory leak — agent sees OOM crash on the service itself
    {"scenario": "memory_leak", "service": "notification-service",
     "expected_root_service": "notification-service"},
    {"scenario": "memory_leak", "service": "api-gateway",
     "expected_root_service": "api-gateway"},

    # Bad deployment — immediate error spike on the deployed service
    {"scenario": "bad_deployment", "service": "payment-service",
     "expected_root_service": "payment-service"},
    {"scenario": "bad_deployment", "service": "order-service",
     "expected_root_service": "order-service"},

    # Dependency cascade — SendGrid down, notification-service fails
    {"scenario": "dependency_cascade", "service": "notification-service",
     "expected_root_service": "notification-service"},

    # Cache stampede — database overwhelmed after cache loss
    {"scenario": "cache_stampede", "service": "inventory-service",
     "expected_root_service": "inventory-service"},
    {"scenario": "cache_stampede", "service": "order-service",
     "expected_root_service": "order-service"},

    # Auth degradation — system-wide latency, root is auth-service
    {"scenario": "auth_degradation", "service": "auth-service",
     "expected_root_service": "auth-service"},
]


def extract_root_service(root_cause_text: str) -> Optional[str]:
    """
    Extracts the root cause service from the agent's diagnosis text.
    
    Finds which known service name appears EARLIEST in the text.
    The root cause service is almost always mentioned first —
    "order-service experienced X, causing payment-service to fail"
    → order-service is the root cause, mentioned first.
    """
    if not root_cause_text:
        return None

    root_cause_lower = root_cause_text.lower()
    all_services = get_all_service_names()

    # Find the position of each service name in the text
    # Return the one that appears earliest (lowest index)
    earliest_pos = len(root_cause_lower) + 1
    earliest_service = None

    for service in all_services:
        pos = root_cause_lower.find(service.lower())
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
            earliest_service = service

    return earliest_service


async def run_test_case(test_case: dict, case_num: int) -> dict:
    """
    Runs the full pipeline for one test case and returns the result.
    """
    scenario = test_case["scenario"]
    service = test_case["service"]
    expected = test_case["expected_root_service"]

    print(f"\n[{case_num}/{len(TEST_CASES)}] {scenario} on {service}")
    print(f"  Expected root service: {expected}")

    # Generate incident data for this specific scenario and service
    start_time = datetime.now(UTC)
    incident_data = generate_incident_data(
        scenario_name=scenario,
        service_name=service,
        start_time=start_time,
    )

    # Create a fake incident ID for this test
    test_incident_id = uuid.uuid4()

    # Ingest logs into pgvector
    async with AsyncSessionLocal() as db:
        await ingest_logs(
            incident_id=test_incident_id,
            logs=incident_data["logs"],
            db=db,
        )
        await db.commit()

    # Build initial state for the agents
    alert = incident_data["alert_payload"]
    initial_state = {
        "incident_id": str(test_incident_id),
        "affected_service": alert["affected_service"],
        "severity": alert["severity"],
        "raw_alert": alert["raw_alert"],
        "logs": incident_data["logs"],
        "metrics": incident_data["metrics"],
        "triage_findings": None,
        "log_findings": None,
        "metrics_findings": None,
        "root_cause": None,
        "confidence_score": None,
        "remediation_steps": None,
        "agent_report": None,
        "messages": [],
    }

    # Run the agent pipeline
    final_state = await incident_graph.ainvoke(initial_state)

    root_cause = final_state.get("root_cause", "")
    confidence = final_state.get("confidence_score", 0)
    identified_service = extract_root_service(root_cause)
    correct = identified_service == expected

    print(f"  Root cause: {root_cause[:80]}...")
    print(f"  Identified service: {identified_service}")
    print(f"  Confidence: {confidence}")
    print(f"  Result: {'✅ CORRECT' if correct else '❌ WRONG'}")

    return {
        "scenario": scenario,
        "service": service,
        "expected": expected,
        "identified": identified_service,
        "root_cause": root_cause,
        "confidence": confidence,
        "correct": correct,
    }


async def run_evaluation():
    """
    Runs all test cases and prints a summary report.
    """
    print("=" * 60)
    print("INCIDENT WHISPERER — EVALUATION HARNESS")
    print("=" * 60)
    print(f"Running {len(TEST_CASES)} test cases...")

    results = []
    for i, test_case in enumerate(TEST_CASES, 1):
        result = await run_test_case(test_case, i)
        results.append(result)

    # --- Summary ---
    correct = sum(1 for r in results if r["correct"])
    total = len(results)
    accuracy = correct / total * 100

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    # Per-scenario breakdown
    scenarios_seen = {}
    for r in results:
        s = r["scenario"]
        if s not in scenarios_seen:
            scenarios_seen[s] = {"correct": 0, "total": 0}
        scenarios_seen[s]["total"] += 1
        if r["correct"]:
            scenarios_seen[s]["correct"] += 1

    print("\nPer-scenario accuracy:")
    for scenario, counts in scenarios_seen.items():
        pct = counts["correct"] / counts["total"] * 100
        print(f"  {scenario:<35} {counts['correct']}/{counts['total']} ({pct:.0f}%)")

    print(f"\nOverall accuracy: {correct}/{total} ({accuracy:.1f}%)")
    print("=" * 60)

    # Failed cases
    failed = [r for r in results if not r["correct"]]
    if failed:
        print("\nFailed cases:")
        for r in failed:
            print(f"  {r['scenario']} on {r['service']}")
            print(f"    Expected: {r['expected']}")
            print(f"    Got:      {r['identified']}")
            print(f"    Text:     {r['root_cause'][:60]}...")

    return accuracy, results


if __name__ == "__main__":
    asyncio.run(run_evaluation())