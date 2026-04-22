"""API endpoint smoke tests for room creation and listing."""

import sys
import uuid

import pytest
from starlette.websockets import WebSocketDisconnect

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


def test_websocket_room_join_success_sends_game_state() -> None:
    """Direct room websocket joins should send connected and game_state messages."""
    request_payload = {
        "name": "WS Join Success Room",
        "small_blind": 10,
        "big_blind": 20,
        "min_players": 2,
        "starting_chips": 1000,
    }

    with TestClient(app) as client:
        create_response = client.post("/api/rooms", json=request_payload)
        assert create_response.status_code == 201
        room_id = create_response.json()["id"]

        with client.websocket_connect(
            f"/ws/game/{room_id}?player_name=Alice"
        ) as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"
            assert connected["data"]["name"] == "Alice"

            game_state = websocket.receive_json()
            assert game_state["type"] == "game_state"
            assert game_state["data"]["room"]["id"] == room_id
            assert game_state["data"]["room"]["player_count"] == 1


def test_websocket_room_join_failure_sends_reason_and_closes() -> None:
    """Invalid direct room joins should send ROOM_NOT_FOUND and close the socket."""
    missing_room_id = f"missing-{uuid.uuid4().hex[:8]}"

    with TestClient(app) as client:
        with client.websocket_connect(
            f"/ws/game/{missing_room_id}?player_name=Bob"
        ) as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"

            error_message = websocket.receive_json()
            assert error_message["type"] == "error"
            assert error_message["data"]["code"] == "ROOM_NOT_FOUND"
            assert error_message["data"]["message"] == "Room not found"

            with pytest.raises(WebSocketDisconnect) as disconnect_info:
                websocket.receive_json()

            assert disconnect_info.value.code == 1008
