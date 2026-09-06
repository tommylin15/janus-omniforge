"""One-shot GCP dev acceptance for the real Private GCS/Iceberg store."""

from __future__ import annotations

from uuid import uuid4

from .assistant_storage import safe_private_record
from .store import PrivateIcebergStore


def run() -> None:
    store=PrivateIcebergStore.from_env()
    owner_a,owner_b=uuid4(),uuid4()
    record={"event_id":f"acceptance-{uuid4()}","seq":0,"thread_id":"acceptance-thread",
            "turn_id":"acceptance-turn","event_type":"text_delta","payload":{"text":"private"},
            "item_id":None,"provider_ids":{}}
    try:
        store.write_assistant_event(user_id=owner_a,record=record)
        store.write_assistant_event(user_id=owner_b,record={**record,"payload":{"text":"isolated"}})
        assert store.read_assistant_event(owner_a,record["thread_id"],record["event_id"])["payload"] == {"text":"private"}
        assert store.read_assistant_event(owner_b,record["thread_id"],record["event_id"])["payload"] == {"text":"isolated"}
        store.write_skill_revision(user_id=owner_a,skill_id="acceptance-skill",revision=1,
                                   definition={"prompt":"bounded","required_tools":["research__echo"],"workflow":[]},
                                   content_digest="sha256:"+"a"*64)
        assert store.export_assistant(owner_a)["assistant_skill_revisions"]
        try: safe_private_record({"api_key":"must-not-persist"})
        except ValueError: pass
        else: raise AssertionError("credential-shaped field was accepted")
    finally:
        store.delete_user(owner_a)
        store.delete_user(owner_b)
        assert store.read_assistant_event(owner_a,record["thread_id"],record["event_id"]) is None
        assert store.read_assistant_event(owner_b,record["thread_id"],record["event_id"]) is None


if __name__ == "__main__": run()
