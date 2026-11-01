import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from resourcing_assistant.app import create_app
from resourcing_assistant.config import Settings
from tests.test_agent import ScriptedGateway


def app(tmp_path, gateway=None):
    return create_app(
        Settings(runtime=tmp_path, reference_date="2026-04-01T00:00:00Z"),
        gateway or ScriptedGateway(),
    )


def test_contract_history_decision_and_validation(tmp_path):
    with TestClient(app(tmp_path)) as c:
        assert c.get("/threads/missing").status_code == 404
        thread = c.post("/threads", json={}).json()["thread_id"]
        assert c.get("/threads").json()[0]["thread_id"] == thread
        assert (
            c.post(
                f"/threads/{thread}/messages", json={"request_id": "r1", "text": "  "}
            ).status_code
            == 422
        )
        response = c.post(
            f"/threads/{thread}/messages", json={"request_id": "r1", "text": "book"}
        )
        assert response.status_code == 200, response.text
        action = response.json()["blocks"][0]["action_id"]
        assert (
            c.post(
                f"/threads/{thread}/confirm",
                json={"action_id": action, "decision": "confirm", "hours": 999},
            ).status_code
            == 422
        )
        assert (
            c.post(
                f"/threads/{thread}/confirm",
                json={"action_id": action, "decision": "confirm"},
            ).status_code
            == 200
        )
        history = c.get(f"/threads/{thread}").json()
        assert history["messages"][1]["content"]["blocks"][0]["status"] == "confirmed"
        assert (
            c.post(
                f"/threads/{thread}/messages", json={"request_id": "r1", "text": "book"}
            ).json()["blocks"][0]["status"]
            == "confirmed"
        )
        assert (
            c.post(
                f"/threads/{thread}/messages",
                json={"request_id": "r1", "text": "changed"},
            ).status_code
            == 409
        )
        assert c.get("/health").json()["status"] == "alive"


def test_one_active_operation_and_other_thread_progresses(tmp_path):
    entered = threading.Event()
    release = threading.Event()

    class SlowGateway(ScriptedGateway):
        def call(self, name, **inputs):
            if name == "InterpretRequest" and inputs["message"] == "slow":
                entered.set()
                release.wait(5)
            return super().call(name, **inputs)

    with TestClient(app(tmp_path, SlowGateway())) as c:
        thread = c.post("/threads", json={}).json()["thread_id"]
        other = c.post("/threads", json={}).json()["thread_id"]
        with ThreadPoolExecutor() as pool:
            work = pool.submit(
                c.post,
                f"/threads/{thread}/messages",
                json={"request_id": "r1", "text": "slow"},
            )
            assert entered.wait(3)
            try:
                duplicate = c.post(
                    f"/threads/{thread}/messages",
                    json={"request_id": "r1", "text": "slow"},
                )
                assert duplicate.status_code == 202
                assert (
                    c.post(
                        f"/threads/{thread}/messages",
                        json={"request_id": "r2", "text": "count"},
                    ).status_code
                    == 409
                )
                assert (
                    c.post(
                        f"/threads/{other}/messages",
                        json={"request_id": "r1", "text": "count"},
                    ).status_code
                    == 200
                )
            finally:
                release.set()
            assert work.result().status_code == 200
