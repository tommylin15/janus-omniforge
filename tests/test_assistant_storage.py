from pathlib import Path
import shutil
import unittest
from uuid import UUID, uuid4

from services.api.assistant_storage import AssistantStorage, safe_private_record
from services.api.engine_security import AgentEvent, AgentEventType
from services.api.repository import ConflictError
from services.api.store import PrivateIcebergStore


ROOT=Path(__file__).parents[1]
USER_A=UUID("00000000-0000-0000-0000-000000000001")
USER_B=UUID("00000000-0000-0000-0000-000000000002")


class Repository:
    def __init__(self): self.row=None; self.completed=[]
    def reserve_assistant_event(self,user_id,event,key,digest):
        candidate={"user_id":user_id,"thread_id":event.thread_id,"event_id":event.event_id,
                   "payload_digest":digest,"status":"PENDING"}
        if self.row is None: self.row=candidate
        return self.row
    def complete_assistant_event(self,user_id,thread_id,event_id,ref):
        self.completed.append((user_id,thread_id,event_id,ref))
        self.row.update(status="PERSISTED",artifact_ref=ref)


class Store:
    def __init__(self): self.records=[]
    def write_assistant_event(self,**value):
        self.records.append(value)
        return f"private.assistant_events/{value['record']['thread_id']}/{value['record']['event_id']}"

    def write_skill_revision(self, **value):
        self.skill = value
        return f"private.assistant_skill_revisions/{value['skill_id']}/{value['revision']}"


class AssistantStorageTest(unittest.TestCase):
    def test_skill_manifest_is_versioned_and_cannot_use_undeclared_workflow_tools(self):
        repository, store = Repository(), Store()
        repository.reserve_skill_revision = lambda *args: {
            "content_digest": args[-1], "status": "PENDING",
        }
        repository.complete_skill_revision = lambda *args: None
        storage = AssistantStorage(repository, store)
        result = storage.write_skill_revision(
            USER_A, "research", 1,
            {"prompt": "Summarize", "required_tools": ["research__search"],
             "workflow": [{"tool": "research__search", "args": {"limit": 5}}]},
            "skill-key",
        )
        self.assertEqual(result["status"], "PERSISTED")
        self.assertEqual(store.skill["definition"]["required_tools"], ["research__search"])
        with self.assertRaises(ValueError):
            storage.write_skill_revision(USER_A, "unsafe", 1,
                {"prompt": "Run", "workflow": [{"tool": "shell"}]}, "unsafe-key")
        with self.assertRaises(ValueError):
            storage.write_skill_revision(USER_A, "secret", 1,
                {"prompt": "No", "required_tools": ["research__search"],
                 "workflow": [{"tool": "research__search", "args": {"api_key": "x"}}]}, "secret-key")

    def test_event_replay_is_an_idempotent_upsert_and_digest_collision_fails(self):
        repository,store=Repository(),Store()
        storage=AssistantStorage(repository,store)
        event=AgentEvent("event-1",0,"thread-1","turn-1",AgentEventType.TEXT_DELTA,{"text":"hello"})
        first=storage.append_event(USER_A,event,"event-key")
        second=storage.append_event(USER_A,event,"event-key")
        self.assertEqual(first["artifact_ref"],second["artifact_ref"])
        self.assertEqual(len(repository.completed),1)
        self.assertEqual(len(store.records),1)
        changed=AgentEvent("event-1",0,"thread-1","turn-1",AgentEventType.TEXT_DELTA,{"text":"changed"})
        with self.assertRaises(ConflictError): storage.append_event(USER_A,changed,"event-key")

    def test_credential_shaped_fields_fail_closed_but_usage_counts_are_allowed(self):
        self.assertEqual(safe_private_record({"usage":{"input_tokens":3}}),{"usage":{"input_tokens":3}})
        for value in ({"api_key":"x"},{"nested":{"refresh_token":"x"}},{"raw_provider_error":"x"}):
            with self.assertRaises(ValueError): safe_private_record(value)

    def test_private_iceberg_assistant_records_are_owner_scoped_and_deletable(self):
        from pyiceberg.catalog.sql import SqlCatalog

        root=Path(".tmp")/f"assistant-storage-{uuid4()}"; root.mkdir(parents=True)
        catalog=None
        try:
            warehouse=(root/"warehouse").as_posix()
            catalog=SqlCatalog("test",uri="sqlite:///"+(root.resolve()/"catalog.db").as_posix(),warehouse=warehouse)
            store=PrivateIcebergStore(catalog,warehouse)
            record={"event_id":"event-1","seq":0,"thread_id":"thread-1","turn_id":"turn-1",
                    "event_type":"text_delta","payload":{"text":"mine"},"item_id":None,"provider_ids":{}}
            store.write_assistant_event(user_id=USER_A,record=record)
            store.write_assistant_event(user_id=USER_B,record={**record,"payload":{"text":"other"}})
            self.assertEqual(store.read_assistant_event(USER_A,"thread-1","event-1")["payload"],{"text":"mine"})
            self.assertEqual(store.read_assistant_event(USER_B,"thread-1","event-1")["payload"],{"text":"other"})
            store.delete_user(USER_A)
            self.assertIsNone(store.read_assistant_event(USER_A,"thread-1","event-1"))
            self.assertIsNotNone(store.read_assistant_event(USER_B,"thread-1","event-1"))
        finally:
            if catalog is not None: catalog.engine.dispose()
            shutil.rmtree(root)

    def test_postgres_index_is_owner_leading_bounded_and_contains_no_private_body(self):
        sql=(ROOT/"infra/postgres/migrations/016_private_assistant_storage.sql").read_text(encoding="utf-8")
        self.assertIn("assistant_events_user_thread_seq_idx ON private.assistant_event_index(user_id, thread_id, seq)",sql)
        self.assertIn("UNIQUE (user_id, thread_id, idempotency_key)",sql)
        self.assertIn("payload_digest",sql)
        self.assertNotIn("message_body",sql)
        self.assertNotIn("prompt_fragment",sql)
        self.assertNotIn("credential_ref",sql)

    def test_codex_deletion_cannot_be_marked_complete_before_external_auth_cleanup(self):
        from datetime import date
        from services.api.private_pipeline import PrivatePipeline

        calls=[]
        class DeletionRepository:
            def pipeline_checkpoint(self): return 0
            def pipeline_batch(self,checkpoint,limit): return []
            def pending_deletions(self): return [{"request_id":"request-1","user_id":USER_A}]
            def assistant_cleanup_required(self,user_id): return True
            def mark_deletion_cleanup_pending(self,request_id,user_id): calls.append(("pending",user_id))
            def complete_deletion(self,request_id,user_id): calls.append(("complete",user_id))
        class DeletionStore:
            def delete_user(self,user_id): calls.append(("iceberg",user_id))

        PrivatePipeline(DeletionRepository(),DeletionStore(),lambda symbols,when:{}).run(date(2026,9,6))
        self.assertEqual(calls,[("iceberg",USER_A),("pending",USER_A)])

    def test_deletion_completes_without_external_cleanup_when_no_assistant_state_exists(self):
        from datetime import date
        from services.api.private_pipeline import PrivatePipeline

        calls=[]
        class DeletionRepository:
            def pipeline_checkpoint(self): return 0
            def pipeline_batch(self,checkpoint,limit): return []
            def pending_deletions(self): return [{"request_id":"request-1","user_id":USER_A}]
            def assistant_cleanup_required(self,user_id): return False
            def complete_deletion(self,request_id,user_id): calls.append(("complete",user_id))
        class DeletionStore:
            def delete_user(self,user_id): calls.append(("iceberg",user_id))

        PrivatePipeline(DeletionRepository(),DeletionStore(),lambda symbols,when:{}).run(date(2026,9,6))
        self.assertEqual(calls,[("iceberg",USER_A),("complete",USER_A)])


if __name__ == "__main__": unittest.main()
