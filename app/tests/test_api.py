"""API behaviour: thin endpoints, one error shape, HTTP-level atomicity."""

from __future__ import annotations


def _create_board(client, key: str = "TF"):
    return client.post("/api/v1/boards", json={"key": key, "name": "TaskFlow"})


def _create_task(client, **overrides):
    payload = {"board_id": 1, "title": "Original title", **overrides}
    return client.post("/api/v1/tasks", json=payload)


# --- probes -----------------------------------------------------------------


def test_liveness_touches_nothing(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_ready_and_startup_with_database(client):
    for endpoint in ("/readyz", "/startupz"):
        response = client.get(endpoint)
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok", "database": "ok"}


def test_ready_and_startup_fail_without_database(broken_db_client):
    for endpoint in ("/readyz", "/startupz"):
        response = broken_db_client.get(endpoint)
        assert response.status_code == 503
        assert response.get_json() == {
            "status": "unavailable",
            "database": "unreachable",
        }
    # liveness must not care that the database is gone
    assert broken_db_client.get("/healthz").status_code == 200


# --- endpoints ---------------------------------------------------------------


def test_board_create_and_fetch(client):
    created = _create_board(client, key="tf")
    assert created.status_code == 201
    assert created.get_json()["key"] == "TF"
    assert client.get("/api/v1/boards").get_json()["boards"][0]["key"] == "TF"
    assert client.get("/api/v1/boards/1").status_code == 200


def test_task_lifecycle(client):
    _create_board(client)
    created = _create_task(client)
    assert created.status_code == 201
    assert created.get_json()["reference"] == "TF-1"

    patched = client.patch("/api/v1/tasks/1", json={"status": "in_progress"})
    assert patched.status_code == 200
    assert patched.get_json()["status"] == "in_progress"

    assert client.delete("/api/v1/tasks/1").status_code == 204
    assert client.get("/api/v1/tasks/1").status_code == 404


def test_task_filters(client):
    _create_board(client)
    _create_task(client, title="A", assignee="moshe")
    _create_task(client, title="B")
    filtered = client.get("/api/v1/tasks?assignee=moshe").get_json()["tasks"]
    assert [t["title"] for t in filtered] == ["A"]


# --- the rollback rule -------------------------------------------------------


def test_patch_is_atomic_when_transition_is_illegal(client):
    """A PATCH carrying a valid title and an illegal status changes nothing."""
    _create_board(client)
    _create_task(client)

    response = client.patch(
        "/api/v1/tasks/1",
        json={"title": "SHOULD NOT PERSIST", "status": "done"},
    )
    assert response.status_code == 409

    fetched = client.get("/api/v1/tasks/1").get_json()
    assert fetched["title"] == "Original title"
    assert fetched["status"] == "todo"


# --- the error shape ---------------------------------------------------------


def test_error_shape_is_uniform_across_404_409_422(client):
    _create_board(client)
    _create_task(client)

    responses = {
        404: client.get("/api/v1/tasks/999"),
        409: client.patch("/api/v1/tasks/1", json={"status": "done"}),
        422: client.post("/api/v1/boards", json={"key": "x", "name": "Bad"}),
    }
    for status, response in responses.items():
        assert response.status_code == status
        body = response.get_json()
        assert set(body) == {"error"}
        assert {"code", "message"} <= set(body["error"])
        assert isinstance(body["error"]["code"], str)
        assert isinstance(body["error"]["message"], str)

    details = responses[409].get_json()["error"]["details"]
    assert details["allowed"] == ["blocked", "in_progress"]
    assert details["current"] == "todo"
    assert details["requested"] == "done"


def test_unknown_url_shares_the_shape(client):
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_duplicate_board_key_is_409(client):
    _create_board(client)
    response = _create_board(client)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "conflict"
