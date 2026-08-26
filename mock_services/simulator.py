import random
from datetime import datetime, UTC
from mock_services.services import (
    get_all_service_names,
    get_services_with_database,
    get_service,
)
from mock_services.scenarios import (
    connection_pool,
    memory_leak,
    bad_deployment,
    dependency_cascade,
    cache_stampede,
    auth_degradation,
)

# Each scenario defines:
# - which services it applies to
# - the module that generates its data
SCENARIO_REGISTRY = {
    "connection_pool_exhaustion": {
        "module": connection_pool,
        "applicable_services": get_services_with_database,
        "description": "Database connection pool exhausted — cascade to dependents",
    },
    "memory_leak": {
        "module": memory_leak,
        "applicable_services": get_all_service_names,
        "description": "Memory leak causing gradual degradation and OOM crash",
    },
    "bad_deployment": {
        "module": bad_deployment,
        "applicable_services": get_all_service_names,
        "description": "Bad deployment causing immediate error rate spike",
    },
    "dependency_cascade": {
        "module": dependency_cascade,
        "applicable_services": lambda: ["notification-service"],
        "description": "External API (SendGrid) timeout causing notification queue backup",
    },
    "cache_stampede": {
        "module": cache_stampede,
        "applicable_services": get_services_with_database,
        "description": "Cache expiry causing database stampede",
    },
    "auth_degradation": {
        "module": auth_degradation,
        "applicable_services": lambda: ["auth-service"],
        "description": "Auth service degradation causing system-wide latency spike",
    },
}


def pick_random_scenario() -> tuple[str, str]:
    scenario_name = random.choice(list(SCENARIO_REGISTRY.keys()))
    scenario = SCENARIO_REGISTRY[scenario_name]

    # Get applicable services for this scenario
    applicable = scenario["applicable_services"]()
    service_name = random.choice(applicable)

    return scenario_name, service_name


def generate_incident_data(
    scenario_name: str = None,
    service_name: str = None,
    start_time: datetime = None,
) -> dict:
    if start_time is None:
        start_time = datetime.now(UTC)

    # Pick randomly if not specified
    if scenario_name is None or service_name is None:
        scenario_name, service_name = pick_random_scenario()

    scenario = SCENARIO_REGISTRY[scenario_name]
    module = scenario["module"]

    return {
        "scenario": scenario_name,
        "service": service_name,
        "description": scenario["description"],
        "logs": module.generate_logs(service_name, start_time),
        "metrics": module.generate_metrics(service_name, start_time),
        "alert_payload": module.get_alert_payload(service_name),
    }