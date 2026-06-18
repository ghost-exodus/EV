"""
Integration tests for API rate limiting.
Verifies that /api/v1/* routes enforce a 100/minute limit per authenticated user
and return custom 429 JSON responses.
"""

import pytest
from fastapi import status
from db.models import Battery


def test_rate_limiting_enforced(client, db_session):
    """
    Test that making more than 100 requests within a minute to a rate-limited
    endpoint returns a 429 Too Many Requests status code with custom error message
    and headers.
    """
    # Create the battery entry so the telemetry query returns 200 OK instead of 404
    batt = Battery(battery_id="B0047", vehicle_id="VH_NASA_B0047", nominal_capacity_mah=2000.0)
    db_session.add(batt)
    db_session.commit()

    # Reset the limiter state to ensure isolated execution
    from main import app
    app.state.limiter.reset()

    battery_id = "B0047"
    headers = {"Authorization": "Bearer mock-token"}

    # Perform 100 successful requests (within the rate limit)
    for i in range(100):
        response = client.get(f"/api/v1/telemetry/{battery_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK

    # The 101st request must trigger the 429 Too Many Requests response
    limit_exceeded_response = client.get(f"/api/v1/telemetry/{battery_id}", headers=headers)
    assert limit_exceeded_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # Check custom 429 response body and headers
    json_data = limit_exceeded_response.json()
    assert json_data["error"] == "Rate limit exceeded"
    assert "retry_after_seconds" in json_data
    assert int(json_data["retry_after_seconds"]) > 0

    assert "Retry-After" in limit_exceeded_response.headers
    assert int(limit_exceeded_response.headers["Retry-After"]) > 0


def test_rate_limiting_exemptions(client):
    """
    Test that liveness/readiness checks and internal endpoints are exempt.
    """
    from main import app
    app.state.limiter.reset()

    # Hammer liveness probe 105 times (exceeding 100 limit)
    for _ in range(105):
        res = client.get("/health")
        assert res.status_code == status.HTTP_200_OK

    # Hammer readiness probe 105 times. It can return 200 or 503 depending on SQS reachability
    # in the test environment, but should never return 429.
    for _ in range(105):
        res = client.get("/ready")
        assert res.status_code in (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE)
