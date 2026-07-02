from datetime import datetime, timedelta, UTC
from mock_services.log_generator import create_log, new_trace_id

def generate_connection_pool_incident(start_time: datetime = None) -> list[dict]:
    # full log timeline for a connection pool exhaustion cascading failure
    # order svc has a slow unindexed query
    # connections open for too long
    # pool exhausted
    # multiple incident requests start timing out
    # payment svc, that depends on order svc, starts failing its calls
    # payment svc's error rate crosses a threshold

    if start_time is None:
        start_time = datetime.now(UTC)

    logs = []

    # T=0, root cause- slow query, sys level obs
    # no trace_id as its not tied to 1 specific user req
    logs.append(
        create_log(
            service="order-service",
            level="WARN",
            message="Slow query detected on orders table",
            trace_id="system", #placeholder - represents "not request scoped"
            timestamp=start_time,
            metadata={
                "query_duration_ms": 412,
                "baseline_duration_ms": 10, 
                "table": "orders",
            },
        )
    )

    # T+3 to T+15: 8 indep failing req
    num_failing_requests = 8
    seconds_between_requests = 1.5
    first_request_offset = 3
    for i in range(num_failing_requests):
        trace_id = new_trace_id()
        request_offset = first_request_offset + (i * seconds_between_requests)
        request_time = start_time + timedelta(seconds=request_offset)

        # order-svc pool is exhausted, req has to w8
        logs.append(
            create_log(
                service="order-service",
                level="WARN",
                message="Connection pool exhausted, req waiting",
                trace_id=trace_id,
                timestamp=request_time,
                metadata={
                    "pool_size": 5,
                    "active_connections": 5,
                    "awaiting_requests": i + 1,
                },
            )
        )

        # after waiting, request times out
        timeout_time = request_time + timedelta(seconds=2)
        logs.append(
            create_log(
                service="order-service",
                level="ERROR",
                message="Request timeout waiting for database connection",
                trace_id=trace_id, 
                timestamp=timeout_time,
                metadata={"timeout_seconds": 30, "endpoint": "/orders/verify"},
            )
        )

        # payment-service ki call to order-service failed
        payment_fail_time = timeout_time + timedelta(seconds=0.5)
        logs.append(
            create_log(
                service="payment-service",
                level="ERROR",
                message="Dependency call to order-service failed",
                trace_id=trace_id,
                timestamp=payment_fail_time,
                metadata={
                    "target_service": "order-service",
                    "retry_count": 3,
                    "status_code": 503,
                },
            )
        )

    # sort everything chronologically - since we built it in service-grouped
    # chunks per request, this guarantees the final list is in true time order
    logs.sort(key=lambda log: log["timestamp"])
    return logs