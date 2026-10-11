"""Event labels: synthetic fixtures only, never a claim of real human review."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "jobs/intelligence-mart"))
from intelligence_mart.event_labeling import (
    VERSION, approved_dataset, chronological_oos, from_core_events, rules_baseline,
)


def raw_event(**changes):
    row = {
        "event_id": "2330-1151008-7", "symbol": "2330", "source_id": "twse",
        "provenance_id": "provenance-1", "event_type": "第51款",
        "details": "台積電公布九月份營收。", "published_at": "2026-10-08T13:54:04+08:00",
        "observed_at": "2026-10-08T23:34:51Z", "effective_date": "2026-10-08",
    }
    row.update(changes)
    return row


def human_review(candidate, **changes):
    row = {
        "candidate_id": candidate["candidate_id"], "content_sha": candidate["content_sha"],
        "status": "approved", "label_version": VERSION, "review_method": "human",
        "reviewer": "fixture-reviewer", "reviewed_at": "2026-10-09T00:00:00Z",
        "category": "earnings", "direction": "neutral",
    }
    row.update(changes)
    return row


def test_candidate_generation_dedups_and_keeps_publication_distinct_from_effective_date():
    result = from_core_events([raw_event(), raw_event()], core_snapshot_id="core-fixed")
    assert len(result["candidates"]) == 1
    record = result["candidates"][0]
    assert record["event_id"] == "2330-1151008-7"
    assert record["effective_date"] == "2026-10-08"
    assert record["published_at"].startswith("2026-10-08T05:54:04")
    assert record["reviewer"] is None and record["category"] is None
    assert record["training_authorization_reference"] is None


@pytest.mark.parametrize("change,reason", [
    ({"source_id": "other"}, "unauthorized_source"),
    ({"source_authorization": "blocked"}, "unauthorized_source"),
    ({"provenance_id": ""}, "missing_event_identity_or_text"),
    ({"published_at": None}, "missing_published_at"),
    ({"published_at": "2026-10-08T14:00:00"}, "naive_published_at"),
    ({"published_at": "2026-10-10T00:00:00Z"}, "publication_after_observation"),
])
def test_candidate_fail_closed(change, reason):
    result = from_core_events([raw_event(**change)], core_snapshot_id="core-fixed")
    assert result["candidates"] == []
    assert result["rejected"][0]["reason"] == reason


def test_revision_changes_identity_but_stable_event_group():
    first, second = from_core_events(
        [raw_event(), raw_event(details="修訂之營收公告")],
        core_snapshot_id="core-fixed")["candidates"]
    assert first["event_group_id"] == second["event_group_id"]
    assert first["candidate_id"] != second["candidate_id"]


def fixture_training_grant(**changes):
    grant = {
        "source_id": "twse", "authorization_reference": "TEST-ONLY-permission",
        "status": "approved", "scope": "local_event_classifier_research",
        "approved_by": "fixture-rights-verifier",
        "verified_at": "2026-10-08T00:00:00Z",
        "evidence_uri": "https://example.org/test-only-authorization",
    }
    grant.update(changes)
    return grant


def fixture_approved_rights():
    return {"source_id": "twse", "source_authorization": "official",
            "training_authorization_reference": "TEST-ONLY-permission",
            "training_authorization_verified_by": "fixture-rights-verifier",
            "training_authorization_evidence_uri": "https://example.org/test-only-authorization"}


def test_human_review_and_training_rights_are_both_required():
    candidate = from_core_events([raw_event()], core_snapshot_id="core-fixed")["candidates"][0]
    with pytest.raises(ValueError, match="training_use_not_authorized"):
        approved_dataset([candidate], [human_review(candidate)])
    candidate["training_authorization_reference"] = "TEST-ONLY-permission"
    grant = fixture_training_grant()
    tampered = dict(candidate, text="tampered announcement")
    with pytest.raises(ValueError, match="tampered_candidate"):
        approved_dataset([tampered], [human_review(tampered)], training_grants=[grant])
    labeled = approved_dataset([candidate], [human_review(candidate)], training_grants=[grant])
    assert labeled[0]["review_status"] == "approved"
    assert labeled[0]["training_authorization_verified_by"] == "fixture-rights-verifier"
    for overrides, message in [
        ({"review_method": "rules"}, "human_reviewer_required"),
        ({"reviewer": ""}, "human_reviewer_required"),
        ({"content_sha": "sha256:wrong"}, "label_version_or_revision_mismatch"),
        ({"category": "up"}, "invalid_event_label"),
        ({"reviewed_at": "2026-10-08T04:00:00Z"}, "review_before_observation"),
    ]:
        with pytest.raises(ValueError, match=message):
            approved_dataset([candidate], [human_review(candidate, **overrides)], training_grants=[grant])
    with pytest.raises(ValueError, match="duplicate_review"):
        approved_dataset([candidate], [human_review(candidate), human_review(candidate)], training_grants=[grant])


@pytest.mark.parametrize("change,reason", [
    ({"source_id": "random"}, "invalid_training_grant"),
    ({"status": "approved", "approved_by": ""}, "invalid_training_grant"),
    ({"scope": "public_data_read"}, "invalid_training_grant"),
    ({"evidence_uri": ""}, "invalid_training_grant"),
    ({"verified_at": "2026-10-08"}, "naive_training_grant_verified_at"),
])
def test_unverifiable_training_grant_is_rejected(change, reason):
    candidate = from_core_events([raw_event()], core_snapshot_id="core-fixed")["candidates"][0]
    with pytest.raises(ValueError, match=reason):
        approved_dataset([candidate], [human_review(candidate)], training_grants=[fixture_training_grant(**change)])


def test_wrong_source_grant_or_duplicate_grant_is_blocked():
    candidate = from_core_events([raw_event()], core_snapshot_id="core-fixed")["candidates"][0]
    with pytest.raises(ValueError, match="training_use_not_authorized"):
        approved_dataset([candidate], [human_review(candidate)],
                         training_grants=[fixture_training_grant(source_id="mops")])
    with pytest.raises(ValueError, match="duplicate_training_grant_for_source"):
        approved_dataset([candidate], [human_review(candidate)],
                         training_grants=[fixture_training_grant(), fixture_training_grant()])


def test_no_labels_means_no_probability_or_fake_oos():
    report = chronological_oos([], cutoff="2026-10-01T00:00:00+08:00")
    assert report["status"] == "insufficient_labeled_data"
    assert report["classifier_probability"] is None
    assert not report["publication_authority"]


def test_chronological_holdout_purges_issuer_and_late_training_reviews():
    d = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(16):
        published = d + timedelta(days=i)
        rows.append({
            "candidate_id": f"id-{i}", "event_group_id": f"event-{i}",
            "symbol": "2330" if i in (1, 10) else f"s-{i}",
            "text": "營收大幅增加" if i % 2 else "配息股利公告",
            "category": "earnings" if i % 2 else "dividend",
            "direction": "positive" if i % 2 else "neutral",
            "published_at": published.isoformat(),
            "reviewed_at": (d + timedelta(days=50) if i == 2 else published + timedelta(hours=1)).isoformat(),
            "review_status": "approved", "review_method": "human", "label_version": VERSION,
            **fixture_approved_rights(),
        })
    with pytest.raises(ValueError, match="non_approved_or_unauthorized_label"):
        chronological_oos(rows, cutoff=(d + timedelta(days=10)).isoformat(), min_train=8, min_test=6)
    result = chronological_oos(rows, cutoff=(d + timedelta(days=10)).isoformat(),
                               training_grants=[fixture_training_grant()], min_train=8, min_test=6)
    assert result["status"] == "research_oos_evaluated"
    assert result["train_count"] == 8
    assert result["holdout_count"] == 6
    assert result["excluded_train_count"] == 1
    assert result["model_name"] == "local-char-tfidf-logistic-v1"
    assert result["metrics"]["category"]["rules_macro_f1"] >= 0
    assert result["metrics"]["direction"]["macro_f1"] >= 0
    assert result["classifier_probability"] is None
    assert not result["publication_authority"]


def test_same_issuer_in_every_fold_blocks_oos():
    d = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = [
        {"candidate_id": str(i), "event_group_id": str(i), "symbol": "2330",
         "text": "營收公告", "category": "earnings", "direction": "neutral",
         "published_at": (d + timedelta(days=i)).isoformat(),
         "reviewed_at": (d + timedelta(days=i, hours=1)).isoformat(),
         "review_status": "approved", "review_method": "human",
         "label_version": VERSION, **fixture_approved_rights()}
        for i in range(40)
    ]
    result = chronological_oos(records, cutoff=(d + timedelta(days=30)).isoformat(),
                               training_grants=[fixture_training_grant()], min_train=1, min_test=1)
    assert result["status"] == "insufficient_labeled_data"
    assert result["train_count"] == 0


def test_rules_are_only_unreviewed_baseline():
    assert rules_baseline("預告法人說明會") == {"category": "investor_meeting", "direction": "uncertain"}


def test_unseen_holdout_class_is_penalized_in_full_taxonomy_brier():
    d = datetime(2026, 2, 1, tzinfo=timezone.utc)
    records = []
    for i in range(12):
        holdout = i >= 10
        records.append({
            "candidate_id": f"new-{i}", "event_group_id": f"group-{i}",
            "symbol": f"hold-{i}" if holdout else f"train-{i}",
            "text": "營收超出預期" if i % 2 else "股利發放公告",
            "category": "guidance" if i == 10 else "earnings" if i % 2 else "dividend",
            "direction": "negative" if i == 10 else "positive" if i % 2 else "neutral",
            "published_at": (d + timedelta(days=i)).isoformat(),
            "reviewed_at": (d + timedelta(days=i, hours=1)).isoformat(),
            "review_status": "approved", "review_method": "human",
            "label_version": VERSION, **fixture_approved_rights(),
        })
    result = chronological_oos(records, cutoff=(d + timedelta(days=10)).isoformat(),
                               training_grants=[fixture_training_grant()], min_train=10, min_test=2)
    assert result["status"] == "research_oos_evaluated"
    assert result["metrics"]["category"]["multiclass_brier_uncalibrated"] >= 0.5
    assert result["metrics"]["direction"]["multiclass_brier_uncalibrated"] >= 0.5
    assert result["classifier_probability"] is None


def test_offline_cli_fails_without_rights_and_only_writes_immutable_research(tmp_path):
    import json
    import subprocess

    script = Path(__file__).parents[1] / "scripts/gcp/b9-event-labels.py"
    events = tmp_path / "events.jsonl"
    pool = tmp_path / "candidates.json"
    reviews = tmp_path / "reviews.jsonl"
    rights = tmp_path / "rights.json"
    output = tmp_path / "event-oos.json"
    events.write_text(json.dumps(raw_event(), ensure_ascii=False) + "\n", encoding="utf-8")
    rights.write_text(json.dumps({"schema_version": "event-training-grants-v1", "grants": []}), encoding="utf-8")
    subprocess.run([sys.executable, str(script), "candidates", "--events-jsonl", str(events),
                    "--core-snapshot-id", "core-fixed", "--out", str(pool)], check=True)
    candidate = json.loads(pool.read_text(encoding="utf-8"))["candidates"][0]
    assert candidate["review_status"] == "pending"
    reviews.write_text(json.dumps(human_review(candidate), ensure_ascii=False) + "\n", encoding="utf-8")
    cmd = [sys.executable, str(script), "oos", "--candidates-json", str(pool),
           "--reviews-jsonl", str(reviews), "--training-grants-json", str(rights),
           "--cutoff", "2026-11-01T00:00:00+08:00", "--out", str(output)]
    denied = subprocess.run(cmd, capture_output=True, text=True)
    assert denied.returncode != 0 and "training_use_not_authorized" in denied.stderr
    assert not output.exists()
    reviews.write_text("", encoding="utf-8")
    subprocess.run(cmd, check=True)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "insufficient_labeled_data"
    assert report["classifier_probability"] is None
    assert report["approved_label_count"] == 0
    repeated = subprocess.run(cmd, capture_output=True, text=True)
    assert repeated.returncode != 0 and "File exists" in repeated.stderr
