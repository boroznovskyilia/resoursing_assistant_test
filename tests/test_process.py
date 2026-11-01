import os
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import httpx


@contextmanager
def server(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log = (tmp_path / "server.log").open("a")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.process_app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env={**os.environ, "TEST_RUNTIME": str(tmp_path)},
        stdout=log,
        stderr=log,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        try:
            if httpx.get(base + "/health", timeout=0.3).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    else:
        process.kill()
        process.wait()
        raise AssertionError((tmp_path / "server.log").read_text())
    try:
        yield process, base
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        log.close()


def test_actual_process_restart_and_confirm(tmp_path):
    with server(tmp_path) as (process, base):
        thread = httpx.post(base + "/threads", json={}).json()["thread_id"]
        proposed = httpx.post(
            f"{base}/threads/{thread}/messages",
            json={"request_id": "r1", "text": "book"},
            timeout=10,
        )
        assert proposed.status_code == 200, proposed.text
        action = proposed.json()["blocks"][0]["action_id"]
        process.kill()
        process.wait()
    with server(tmp_path) as (_, base):
        calls = (tmp_path / "test-model-calls").read_text()
        assert (
            httpx.get(f"{base}/threads/{thread}").json()["pending_action"]["action_id"]
            == action
        )
        assert (tmp_path / "test-model-calls").read_text() == calls
        one = httpx.post(
            f"{base}/threads/{thread}/confirm",
            json={"action_id": action, "decision": "confirm"},
            timeout=10,
        )
        two = httpx.post(
            f"{base}/threads/{thread}/confirm",
            json={"action_id": action, "decision": "confirm"},
            timeout=10,
        )
        assert one.status_code == 200, one.text
        assert (
            one.json()["blocks"][0]["booking_id"]
            == two.json()["blocks"][0]["booking_id"]
        )
        assert (tmp_path / "test-model-calls").read_text() == calls


def test_kill_mid_node_get_does_not_resume_and_explicit_continue(tmp_path):
    with server(tmp_path) as (process, base):
        thread = httpx.post(base + "/threads", json={}).json()["thread_id"]
        with ThreadPoolExecutor() as pool:
            future = pool.submit(
                httpx.post,
                f"{base}/threads/{thread}/messages",
                json={"request_id": "r1", "text": "hang"},
                timeout=12,
            )
            deadline = time.monotonic() + 5
            while not (tmp_path / "entered").exists() and time.monotonic() < deadline:
                time.sleep(0.03)
            assert (tmp_path / "entered").exists()
            process.kill()
            process.wait()
            try:
                future.result()
            except httpx.HTTPError:
                pass
    with server(tmp_path) as (_, base):
        calls = (tmp_path / "test-model-calls").read_text()
        history = httpx.get(f"{base}/threads/{thread}").json()
        assert history["requests"][0]["status"] == "interrupted"
        assert (tmp_path / "test-model-calls").read_text() == calls
        blocked = httpx.post(
            f"{base}/threads/{thread}/messages",
            json={"request_id": "r2", "text": "count"},
            timeout=5,
        )
        assert blocked.status_code == 409
        result = httpx.post(
            f"{base}/threads/{thread}/requests/r1/resume", json={}, timeout=10
        )
        assert result.status_code == 200, result.text
        history = httpx.get(f"{base}/threads/{thread}").json()
        assert len([m for m in history["messages"] if m["role"] == "user"]) == 1
        assert history["requests"][0]["status"] == "completed"
