"""API endpoint smoke tests for room creation and listing."""

import sys

sys.path.append("..")

from fastapi.testclient import TestClient

from app.main import app


def test_root_endpoint_is_available() -> None:
    """Root endpoint should report server status."""
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert payload["api"] == "/api"


def test_create_room_and_list_rooms() -> None:
    """POST /api/rooms should create a room that appears in GET /api/rooms."""
    request_payload = {
        "name": "Connectivity Test Room",
        "small_blind": 10,
        "big_blind": 20,
        "min_players": 2,
        "starting_chips": 1000,
    }

    with TestClient(app) as client:
        create_response = client.post("/api/rooms", json=request_payload)

        assert create_response.status_code == 201
        created_room = create_response.json()
        assert created_room["name"] == request_payload["name"]
        assert created_room["small_blind"] == request_payload["small_blind"]
        assert created_room["big_blind"] == request_payload["big_blind"]

        list_response = client.get("/api/rooms")

    assert list_response.status_code == 200
    rooms_payload = list_response.json()
    assert rooms_payload["total"] >= 1
    assert any(room["id"] == created_room["id"] for room in rooms_payload["rooms"])
