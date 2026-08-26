# mock_services/services.py
# Central registry of all services in our mock microservice cluster.
# Every scenario reads from this to know what services exist 

SERVICES = {
    "order-service": {
        "has_database": True,
        "database_name": "orders_db",
        "dependencies": ["payment-service", "inventory-service"],
        "role": "transactional",
        "typical_rps": 500,
    },
    "payment-service": {
        "has_database": True,
        "database_name": "payments_db",
        "dependencies": ["auth-service"],
        "role": "critical",
        "typical_rps": 300,
    },
    "auth-service": {
        "has_database": True,
        "database_name": "users_db",
        "dependencies": [],
        "role": "foundation",
        "typical_rps": 1200,
    },
    "inventory-service": {
        "has_database": True,
        "database_name": "inventory_db",
        "dependencies": [],
        "role": "transactional",
        "typical_rps": 200,
    },
    "notification-service": {
        "has_database": False,
        "database_name": None,
        "dependencies": [],
        "external_dependencies": ["sendgrid-api", "twilio-api"],
        "role": "async-worker",
        "typical_rps": 100,
    },
    "api-gateway": {
        "has_database": False,
        "database_name": None,
        "dependencies": ["order-service", "auth-service", "inventory-service"],
        "role": "gateway",
        "typical_rps": 2000,
    },
}


def get_service(name: str) -> dict:
    if name not in SERVICES:
        raise ValueError(f"Unknown service: {name}")
    return {**SERVICES[name], "name": name}


def get_services_with_database() -> list[str]:
    return [name for name, cfg in SERVICES.items() if cfg["has_database"]]


def get_all_service_names() -> list[str]:
    return list(SERVICES.keys())


def get_dependents(service_name: str) -> list[str]:
    # Returns services that depend on the given service.
    # Used to generate cascade failure logs.
    return [
        name for name, cfg in SERVICES.items()
        if service_name in cfg["dependencies"]
    ]