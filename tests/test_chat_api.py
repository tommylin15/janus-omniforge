from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from services.api.app import create_app


USER = UUID("00000000-0000-0000-0000-000000000001")


class Repo:
    def __init__(self): self.threads = {}; self.events = {}; self.turns = {}
    def resolve_user(self, _sub, _email): return USER
    def create_assistant_thread(self, user_id, thread_id, binding, *, parent_thread_id=None):
        row = self.threads.setdefault((user_id, thread_id), {
            "user_id": user_id, "thread_id": thread_id, "runtime": binding.runtime.value,
            "model": binding.model, "assistant_profile": binding.assistant_profile,
            "skill_profile": binding.skill_profile, "parent_thread_id": parent_thread_id,
            "status": "ACTIVE", "updated_at": datetime.now(timezone.utc),
        })
        return row
    def assistant_thread(self, user_id, thread_id):
        if (user_id, thread_id) not in self.threads: raise Exception("missing")
        return self.threads[(user_id, thread_id)]
    def assistant_event_for_key(self, user_id, thread_id, key):
        return self.events.get((user_id, thread_id, key))
    def latest_assistant_continuation(self, user_id, thread_id):
        rows = [row for key, row in self.turns.items() if key[:2] == (user_id, thread_id) and row.get("continuation")]
        return rows[-1].get("continuation", {}) if rows else {}
    def start_assistant_turn(self, user_id, thread_id, turn_id, key, **kwargs):
        row = self.turns.setdefault((user_id, thread_id, key), {
            "user_id": user_id, "thread_id": thread_id, "turn_id": turn_id,
            "status": "RUNNING", **kwargs,
        })
        return row
    def finish_assistant_turn(self, user_id, thread_id, turn_id, status, continuation=None):
        row = next(row for key, row in self.turns.items() if key[:2] == (user_id, thread_id) and row["turn_id"] == turn_id)
        row.update(status=status)
        if continuation is not None: row["continuation"] = continuation
        return row
    def next_assistant_seq(self, user_id, thread_id):
        return len([x for x in self.events if x[:2] == (user_id, thread_id)])
    def reserve_assistant_event(self, user_id, event, key, digest):
        row = {"user_id": user_id, "thread_id": event.thread_id, "turn_id": event.turn_id,
               "event_id": event.event_id, "seq": event.seq, "event_type": event.event_type.value,
               "payload_digest": digest, "status": "PENDING", "idempotency_key": key}
        self.events[(user_id, event.thread_id, key)] = row
        return row
    def complete_assistant_event(self, user_id, thread_id, event_id, ref):
        for row in self.events.values():
            if row["user_id"] == user_id and row["thread_id"] == thread_id and row["event_id"] == event_id:
                row.update(status="PERSISTED", artifact_ref=ref)
    def assistant_events_after(self, user_id, thread_id, cursor, limit):
        return [row for row in self.events.values() if row["user_id"] == user_id and row["thread_id"] == thread_id and row["seq"] > cursor][:limit]


class Store:
    def __init__(self): self.rows = {}
    def write_assistant_event(self, *, user_id, record):
        ref = f"private.assistant_events/{record['thread_id']}/{record['event_id']}"
        self.rows[(user_id, record["thread_id"], record["event_id"])] = record
        return ref
    def read_assistant_event(self, user_id, thread_id, event_id):
        return self.rows.get((user_id, thread_id, event_id))


def test_chat_message_is_owner_scoped_and_replayed_as_bounded_sse():
    repo, store = Repo(), Store()
    app = create_app(repo, store, lambda _token, _audience: {
        "iss": "https://accounts.google.com", "aud": "user-client", "sub": "google-a",
        "email": "owner@example.com", "email_verified": True, "exp": 1_900_000_000,
    }, audience="user-client", internal_audience="assistant-internal", internal_callers=frozenset(), mcp=object())
    client = TestClient(app)
    headers = {"Authorization": "Bearer token", "Idempotency-Key": "message-1"}
    assert client.post("/api/v1/me/chats/threads", headers=headers, json={
        "thread_id": "thread-a", "runtime": "gemini", "model": "gemini-2.5-flash",
        "assistant_profile": "default",
    }).status_code == 201
    response = client.post("/api/v1/me/chats/threads/thread-a/messages", headers=headers,
                           json={"content": "hello"})
    assert response.status_code == 202
    replay = client.get("/api/v1/me/chats/threads/thread-a/events?cursor=-1&limit=1", headers=headers)
    assert replay.status_code == 200
    assert "event: item_upsert" in replay.text and '"content":"hello"' in replay.text


def test_codex_message_round_trips_gateway_continuation():
    repo, store, calls = Repo(), Store(), []
    class Gateway:
        def dispatch_assistant_turn(self, owner_id, **request):
            calls.append((owner_id, request))
            return {"events": [{"eventId": f"{request['turn_id']}-done", "type": "turn_completed",
                                 "payload": {"status": "completed"}, "providerIds": {"codexThreadId": "cx-thread"}}],
                    "continuation": {"runtime": "codex", "codexThreadId": "cx-thread", "codexTurnId": request["turn_id"]}}
    app = create_app(repo, store, lambda _token, _audience: {
        "iss": "https://accounts.google.com", "aud": "user-client", "sub": "google-a",
        "email": "owner@example.com", "email_verified": True, "exp": 1_900_000_000,
    }, audience="user-client", internal_audience="assistant-internal", internal_callers=frozenset(), mcp=Gateway())
    client = TestClient(app)
    headers = {"Authorization": "Bearer token"}
    assert client.post("/api/v1/me/chats/threads", headers={**headers, "Idempotency-Key": "thread-1"}, json={
        "thread_id": "codex-thread", "runtime": "codex", "model": "gpt-5", "assistant_profile": "default",
    }).status_code == 201
    first = client.post("/api/v1/me/chats/threads/codex-thread/messages", headers={**headers, "Idempotency-Key": "message-1"}, json={"content": "hello"})
    assert first.status_code == 202
    continuation = first.json()["dispatch"]["continuation"]
    second = client.post("/api/v1/me/chats/threads/codex-thread/messages", headers={**headers, "Idempotency-Key": "message-2"}, json={"content": "continue"})
    assert second.status_code == 202
    assert calls[1][1]["continuation"] == continuation
