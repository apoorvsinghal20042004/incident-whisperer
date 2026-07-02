from datetime import datetime, timedelta, UTC


def generate_metrics(start_time: datetime = None) -> dict:
    """
    Generates time-series metrics for the connection pool exhaustion incident.
    
    Structure: for each metric, we produce a list of {timestamp, value} pairs
    sampled every 10 seconds over a 5-minute window (30 samples total).
    
    The first 2 minutes (12 samples) represent normal baseline behavior.
    The incident starts at T+2min and degrades over the remaining 3 minutes.
    """
    if start_time is None:
        start_time = datetime.now(UTC)

    # Total window: 5 minutes, sampled every 10 seconds
    total_samples = 30
    sample_interval_seconds = 10
    incident_starts_at_sample = 12  # first 12 samples = 2 minutes of baseline

    # Build the timestamp series first — shared across all metrics
    timestamps = [
        start_time + timedelta(seconds=i * sample_interval_seconds)
        for i in range(total_samples)
    ]

    # --- Metric 1: DB connection pool utilization (%) ---
    # Baseline: ~20% (normal traffic uses roughly 1 of 5 connections)
    # Incident: climbs from 20% to 100% over ~90 seconds, stays at 100%
    pool_utilization = []
    for i in range(total_samples):
        if i < incident_starts_at_sample:
            # baseline — small random noise around 20%
            value = 20 + (i % 3)
        else:
            # degradation phase — climbs 10% every sample until capped at 100%
            degradation = (i - incident_starts_at_sample) * 10
            value = min(20 + degradation, 100)
        pool_utilization.append({
            "timestamp": timestamps[i].isoformat(),
            "value": value,
        })

    # --- Metric 2: Average query duration (ms) ---
    # Baseline: ~10ms (fast, indexed queries)
    # Incident: spikes to 400ms+ as the slow query dominates
    query_duration = []
    for i in range(total_samples):
        if i < incident_starts_at_sample:
            # baseline — small variation around 10ms
            value = 10 + (i % 5)
        else:
            # spike — jumps to 400ms and climbs slightly
            spike = (i - incident_starts_at_sample) * 15
            value = min(400 + spike, 500)
        query_duration.append({
            "timestamp": timestamps[i].isoformat(),
            "value": value,
        })

    # --- Metric 3: payment-service error rate (%) ---
    # Baseline: 0% (no errors under normal conditions)
    # Incident: starts climbing ~30 seconds after pool exhaustion
    # Alert threshold: 5% — this is what triggers our incident
    error_rate = []
    for i in range(total_samples):
        if i < incident_starts_at_sample + 3:
            # baseline + small lag before payment-service is affected
            value = 0
        else:
            # error rate climbs as more requests fail
            climb = (i - (incident_starts_at_sample + 3)) * 1.2
            value = round(min(climb, 10.0), 1)
        error_rate.append({
            "timestamp": timestamps[i].isoformat(),
            "value": value,
        })

    return {
        "window_start": start_time.isoformat(),
        "window_end": timestamps[-1].isoformat(),
        "sample_interval_seconds": sample_interval_seconds,
        "metrics": {
            "order_service_db_pool_utilization_pct": pool_utilization,
            "order_service_query_duration_ms": query_duration,
            "payment_service_error_rate_pct": error_rate,
        },
    }