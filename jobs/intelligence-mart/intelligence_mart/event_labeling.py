"""B9 Event/Catalyst: research-only human labels and chronological OOS.

This module never alters Core, deterministic Event specialist, champion or publication.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re

from .facts import APPROVED_SOURCES, canonical_json

VERSION = "event-label-v1"
CATEGORIES = ("earnings", "guidance", "investor_meeting", "dividend", "financing",
              "asset_transaction", "governance", "regulatory", "other")
DIRECTIONS = ("positive", "negative", "neutral", "uncertain")
SOURCE_ALLOWLIST = frozenset({"twse", "mops", "tpex"})


def _timestamp(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing_{name}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid_{name}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"naive_{name}")
    return parsed.astimezone(timezone.utc)


def _sha(value):
    return "sha256:" + sha256(canonical_json(value)).hexdigest()


def from_core_events(rows, *, core_snapshot_id):
    """Create unreviewed candidates. Source approval != training-use permission."""
    if not core_snapshot_id:
        raise ValueError("missing Core snapshot fence")
    accepted, rejected, seen = [], [], set()
    for row in rows:
        event_key = str(row.get("event_id") or "").strip()
        symbol = str(row.get("symbol") or "").strip()
        source = str(row.get("source_id") or "").strip().lower()
        details = row.get("details")
        provenance = str(row.get("provenance_id") or "").strip()
        try:
            if source not in SOURCE_ALLOWLIST or source not in APPROVED_SOURCES:
                raise ValueError("unauthorized_source")
            if row.get("source_authorization", "official") != "official":
                raise ValueError("unauthorized_source")
            if not event_key or not symbol or not provenance or not isinstance(details, str) or not details.strip():
                raise ValueError("missing_event_identity_or_text")
            published = _timestamp(row.get("published_at"), "published_at")
            observed = _timestamp(row.get("observed_at"), "observed_at")
            if published > observed:
                raise ValueError("publication_after_observation")
            content_sha = _sha(details)
            group_id = _sha([source, symbol, event_key])
            identity = _sha([group_id, content_sha])
            if identity in seen:
                continue
            seen.add(identity)
            accepted.append({
                "candidate_id": identity, "event_group_id": group_id, "event_id": event_key,
                "symbol": symbol, "source_id": source, "source_authorization": "official",
                "training_authorization_reference": row.get("training_authorization_reference"),
                "core_snapshot_id": str(core_snapshot_id), "provenance_id": provenance,
                "published_at": published.isoformat(), "observed_at": observed.isoformat(),
                "effective_date": row.get("effective_date"), "source_event_type": row.get("event_type"),
                "content_sha": content_sha, "text": details,
                "review_status": "pending", "label_version": None, "reviewer": None,
                "category": None, "direction": None,
            })
        except ValueError as exc:
            rejected.append({"event_id": event_key or None, "symbol": symbol or None,
                             "reason": str(exc)})
    return {"schema_version": VERSION, "candidates": sorted(accepted, key=lambda r: (r["published_at"], r["candidate_id"])),
            "rejected": rejected, "reviewed_count": 0}


def approved_dataset(candidates, reviews):
    """Only exact revision-matched, explicitly human-reviewed labels can enter research."""
    by_id = {r["candidate_id"]: r for r in candidates}
    if len(by_id) != len(candidates):
        raise ValueError("duplicate_candidate_id")
    approved, seen = [], set()
    for item in reviews:
        cid = item.get("candidate_id")
        if cid in seen:
            raise ValueError("duplicate_review")
        seen.add(cid)
        candidate = by_id.get(cid)
        if candidate is None:
            raise ValueError("unknown_candidate")
        if (_sha(candidate["text"]) != candidate["content_sha"] or
                _sha([candidate["event_group_id"], candidate["content_sha"]]) != cid):
            raise ValueError("tampered_candidate")
        if item.get("status") != "approved":
            continue
        if (item.get("label_version") != VERSION or item.get("content_sha") != candidate["content_sha"]):
            raise ValueError("label_version_or_revision_mismatch")
        if item.get("review_method") != "human" or not str(item.get("reviewer") or "").strip():
            raise ValueError("human_reviewer_required")
        if item.get("category") not in CATEGORIES or item.get("direction") not in DIRECTIONS:
            raise ValueError("invalid_event_label")
        if candidate.get("source_authorization") != "official" or not candidate.get("training_authorization_reference"):
            raise ValueError("training_use_not_authorized")
        reviewed = _timestamp(item.get("reviewed_at"), "reviewed_at")
        observed = _timestamp(candidate.get("observed_at"), "observed_at")
        if reviewed < observed:
            raise ValueError("review_before_observation")
        approved.append({**candidate, "category": item["category"], "direction": item["direction"],
                         "reviewer": item["reviewer"], "review_method": "human",
                         "reviewed_at": reviewed.isoformat(), "review_status": "approved",
                         "label_version": VERSION, "ambiguity_note": item.get("ambiguity_note")})
    return sorted(approved, key=lambda r: (r["published_at"], r["candidate_id"]))


def rules_baseline(text):
    """Deliberately simple deterministic challenger comparator, not ground truth."""
    if re.search(r"法(?:人)?說會|投資人會議", text):
        category = "investor_meeting"
    elif re.search(r"營收|財務報告|每股盈餘|獲利", text):
        category = "earnings"
    elif re.search(r"股利|配息|除息", text):
        category = "dividend"
    elif re.search(r"增資|發行公司債|可轉換公司債", text):
        category = "financing"
    elif re.search(r"取得或處分|使用權資產|不動產", text):
        category = "asset_transaction"
    elif re.search(r"董事改選|獨立董事|董事會", text):
        category = "governance"
    else:
        category = "other"
    return {"category": category, "direction": "uncertain"}


def chronological_oos(approved, *, cutoff, min_train=100, min_test=30):
    """Issuer-disjoint, event-revision-disjoint, time-purged local CPU baseline.

    Labels reviewed after cutoff never enter training. Holdout labels may be
    approved afterward for scoring, but holdout event text is not used for fit.
    """
    boundary = _timestamp(cutoff, "cutoff")
    rows = list(approved)
    ids = [r["candidate_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate_candidates")
    if any(r.get("review_status") != "approved" or r.get("review_method") != "human"
           or r.get("label_version") != VERSION or not r.get("training_authorization_reference")
           for r in rows):
        raise ValueError("non_approved_or_unauthorized_label")
    before = [r for r in rows if _timestamp(r["published_at"], "published_at") < boundary
              and _timestamp(r["reviewed_at"], "reviewed_at") < boundary]
    holdout = [r for r in rows if _timestamp(r["published_at"], "published_at") >= boundary]
    issuers = {r["symbol"] for r in holdout}
    event_groups = {r["event_group_id"] for r in holdout}
    train = [r for r in before if r["symbol"] not in issuers and r["event_group_id"] not in event_groups]
    report = {"protocol": "event-issuer-disjoint-chronological-v1", "label_version": VERSION,
              "cutoff": boundary.isoformat(), "source": "approved-human-reviewed-only",
              "train_count": len(train), "holdout_count": len(holdout),
              "excluded_train_count": len(before) - len(train),
              "holdout_issuer_count": len(issuers), "model_status": "not_verified",
              "publication_authority": False, "classifier_probability": None,
              "category": None, "direction": None}
    if (len(train) < min_train or len(holdout) < min_test or
            len({r["category"] for r in train}) < 2 or
            len({r["direction"] for r in train}) < 2 or
            len({r["category"] for r in holdout}) < 2 or
            len({r["direction"] for r in holdout}) < 2):
        return {**report, "status": "insufficient_labeled_data",
                "reason": "human_labels_or_disjoint_class_support_insufficient"}
    # Pre-installed, locally executed scikit-learn. No remote model or API.
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score, precision_recall_fscore_support

    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4),
                                 min_df=2, max_features=4096, sublinear_tf=True)
    x_train = vectorizer.fit_transform([r["text"] for r in train])
    x_test = vectorizer.transform([r["text"] for r in holdout])
    evaluations = {}
    for field, choices in (("category", CATEGORIES), ("direction", DIRECTIONS)):
        y_train = [r[field] for r in train]
        y_test = [r[field] for r in holdout]
        if len(set(y_train)) < 2:
            return {**report, "status": "insufficient_labeled_data", "reason": field + "_class_support"}
        clf = LogisticRegression(max_iter=200, random_state=17)
        clf.fit(x_train, y_train)
        prediction = clf.predict(x_test).tolist()
        baseline = [rules_baseline(r["text"])[field] for r in holdout]
        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, prediction, labels=list(choices), zero_division=0)
        evaluations[field] = {
            "macro_f1": float(f1_score(y_test, prediction, labels=list(choices), average="macro", zero_division=0)),
            "rules_macro_f1": float(f1_score(y_test, baseline, labels=list(choices), average="macro", zero_division=0)),
            "per_class": {name: {"precision": float(precision[i]), "recall": float(recall[i]),
                                 "f1": float(f1[i]), "support": int(support[i])}
                          for i, name in enumerate(choices)},
        }
    report.update(status="research_oos_evaluated", model_name="local-char-tfidf-logistic-v1",
                  model_status="research_only_not_promoted", metrics=evaluations,
                  holdout_start=min(r["published_at"] for r in holdout),
                  holdout_end=max(r["published_at"] for r in holdout))
    report["evaluation_hash"] = _sha(report)
    return report
