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


def test_human_review_and_training_rights_are_both_required():
    candidate = from_core_events([raw_event()], core_snapshot_id="core-fixed")["candidates"][0]
    with pytest.raises(ValueError, match="training_use_not_authorized"):
        approved_dataset([candidate], [human_review(candidate)])
    candidate["training_authorization_reference"] = "TEST-ONLY-permission"
    tampered = dict(candidate, text="tampered announcement")
    with pytest.raises(ValueError, match="tampered_candidate"):
        approved_dataset([tampered], [human_review(tampered)])
    assert approved_dataset([candidate], [human_review(candidate)])[0]["review_status"] == "approved"
    for overrides, message in [
        ({"review_method": "rules"}, "human_reviewer_required"),
        ({"reviewer": ""}, "human_reviewer_required"),
        ({"content_sha": "sha256:wrong"}, "label_version_or_revision_mismatch"),
        ({"category": "up"}, "invalid_event_label"),
        ({"reviewed_at": "2026-10-08T04:00:00Z"}, "review_before_observation"),
    ]:
        with pytest.raises(ValueError, match=message):
            approved_dataset([candidate], [human_review(candidate, **overrides)])
    with pytest.raises(ValueError, match="duplicate_review"):
        approved_dataset([candidate], [human_review(candidate), human_review(candidate)])


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
            "training_authorization_reference": "TEST-ONLY",
        })
    result = chronological_oos(rows, cutoff=(d + timedelta(days=10)).isoformat(), min_train=8, min_test=6)
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
         "label_version": VERSION, "training_authorization_reference": "TEST-ONLY"}
        for i in range(40)
    ]
    result = chronological_oos(records, cutoff=(d + timedelta(days=30)).isoformat(), min_train=1, min_test=1)
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
            "label_version": VERSION, "training_authorization_reference": "TEST-ONLY",
        })
    result = chronological_oos(records, cutoff=(d + timedelta(days=10)).isoformat(),
                               min_train=10, min_test=2)
    assert result["status"] == "research_oos_evaluated"
    assert result["metrics"]["category"]["multiclass_brier_uncalibrated"] >= 0.5
    assert result["metrics"]["direction"]["multiclass_brier_uncalibrated"] >= 0.5
    assert result["classifier_probability"] is None
