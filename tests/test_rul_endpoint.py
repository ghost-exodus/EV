"""
Unit tests for the GET /api/v1/rul/{battery_id} endpoint.
"""

from db.models import Battery, RULPrediction


def test_rul_endpoint_success(client, db_session):
    """GET /rul/{battery_id} returns latest RUL details for a healthy battery."""
    # Setup database
    battery = Battery(
        battery_id="EV_B0005_001",
        vehicle_id="VH_TESLA_042",
        nominal_capacity_mah=2000.0,
    )
    db_session.add(battery)
    db_session.commit()

    pred = RULPrediction(
        battery_id="EV_B0005_001",
        predicted_rul_cycles=213,
        confidence_lower=188,
        confidence_upper=238,
        model_version="v2.0",
        input_soh_percent=82.4,
    )
    db_session.add(pred)
    db_session.commit()

    response = client.get("/api/v1/rul/EV_B0005_001")
    assert response.status_code == 200

    data = response.json()
    assert data["battery_id"] == "EV_B0005_001"
    assert data["predicted_rul_cycles"] == 213
    assert data["confidence_interval"] == {
        "lower_bound": 188,
        "upper_bound": 238,
        "confidence_percent": 90.0,
    }
    assert data["current_soh_percent"] == 82.4
    assert data["eol_threshold_soh"] == 70.0
    assert data["alert_level"] == "none"


def test_rul_endpoint_alert_warning(client, db_session):
    """GET /rul/{battery_id} returns warning alert when 65 <= SOH < 70."""
    battery = Battery(
        battery_id="EV_B0005_001",
        vehicle_id="VH_TESLA_042",
        nominal_capacity_mah=2000.0,
    )
    db_session.add(battery)
    db_session.commit()

    pred = RULPrediction(
        battery_id="EV_B0005_001",
        predicted_rul_cycles=150,
        confidence_lower=130,
        confidence_upper=170,
        model_version="v2.0",
        input_soh_percent=67.5,
    )
    db_session.add(pred)
    db_session.commit()

    response = client.get("/api/v1/rul/EV_B0005_001")
    assert response.status_code == 200
    assert response.json()["alert_level"] == "warning"


def test_rul_endpoint_alert_critical(client, db_session):
    """GET /rul/{battery_id} returns critical alert when SOH < 65."""
    battery = Battery(
        battery_id="EV_B0005_001",
        vehicle_id="VH_TESLA_042",
        nominal_capacity_mah=2000.0,
    )
    db_session.add(battery)
    db_session.commit()

    pred = RULPrediction(
        battery_id="EV_B0005_001",
        predicted_rul_cycles=90,
        confidence_lower=80,
        confidence_upper=100,
        model_version="v2.0",
        input_soh_percent=62.0,
    )
    db_session.add(pred)
    db_session.commit()

    response = client.get("/api/v1/rul/EV_B0005_001")
    assert response.status_code == 200
    assert response.json()["alert_level"] == "critical"


def test_rul_endpoint_not_found(client):
    """GET /rul/{battery_id} returns 404 if the battery registry does not exist."""
    response = client.get("/api/v1/rul/NON_EXISTENT")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "Battery not found"


def test_rul_endpoint_no_predictions(client, db_session):
    """GET /rul/{battery_id} returns 404 if the battery exists but has no predictions."""
    battery = Battery(
        battery_id="EV_B0005_001",
        vehicle_id="VH_TESLA_042",
        nominal_capacity_mah=2000.0,
    )
    db_session.add(battery)
    db_session.commit()

    response = client.get("/api/v1/rul/EV_B0005_001")
    assert response.status_code == 404
    assert (
        response.json()["detail"]["error"]
        == "No RUL prediction found for this battery"
    )
