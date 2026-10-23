"""Presentation of the controller's persisted schedule, never a second scheduler."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TASKS = {
    "ledger-backup": ("交易資料備份", "備份交易資料，保留可還原的副本。"),
    "ingestion": ("收集市場資料", "取得上市、上櫃行情與公開資料。"),
    "data-supplement": ("補齊缺漏資料", "依現有品質檢查補收缺少的資料。"),
    "mart": ("更新分析結果", "將已收集資料轉成可供網站使用的分析結果。"),
    "market-screening": ("全市場分析", "更新全市場篩選與持股、關注股所需的分析。"),
    "data-quality": ("每週資料檢查", "檢查行情、營收及財報的缺漏與品質。"),
    "private": ("更新個人損益", "用已入帳交易與合格行情更新私人損益。"),
    "stage-cleanup": ("清理過期暫存", "依48小時政策清理過期暫存，保留有效執行引用。"),
    "mobile-ledger": ("處理記帳佇列", "只在有待處理記帳資料時執行。"),
    "iceberg-compaction": ("整理資料檔案", "合併小檔並驗證當前資料可讀。"),
    "core-cleanup": ("清理過期市場資料", "依保留政策與引用保護清理過期資料。"),
    "mart-cleanup": ("清理過期分析結果", "清理過期分析與無現役引用的成果物。"),
    "collection-queue": ("手動收集與資料修復", "處理管理者已驗證、已加入佇列的收集或個股補資料請求。"),
    "analysis-queue": ("手動分析佇列", "處理已核准設定的分析請求；不自行開啟付費模型。"),
}


def stamp(value):
    try:
        point = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return point if point.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def latest_slot(schedule, now):
    local = now.astimezone(ZoneInfo("Asia/Taipei"))
    for offset in range(32):
        day = local - timedelta(days=offset)
        if day.weekday() not in schedule["weekdays"]:
            continue
        if schedule.get("month_days") and day.day not in schedule["month_days"]:
            continue
        for hour in sorted(schedule["hours"], reverse=True):
            slot = day.replace(hour=hour, minute=schedule["minute"], second=0, microsecond=0)
            if slot <= local:
                return slot
    return None


def dashboard(runtime, latest, settings, now=None):
    now = now or datetime.now(timezone.utc)
    observed = stamp(runtime.get("observed_at"))
    fresh = observed is not None and timedelta(0) <= now - observed <= timedelta(hours=2)
    schedules = {row["name"]: row for row in runtime.get("definitions", []) if row.get("name") in TASKS}
    rows = []
    for name, (title, purpose) in TASKS.items():
        schedule = schedules.get(name)
        setting, version = settings.get(name, ({}, 0))
        observed_run = latest.get(name)
        recent = observed_run
        if recent and (stamp(recent.get("scheduled_at")) is None or
                       not now - timedelta(days=7) <= stamp(recent["scheduled_at"]) <= now):
            recent = None
        log = runtime.get("latest_logs", {}).get(name)
        if not recent or not log or log.get("occurrence_id") != recent.get("occurrence_id"):
            log = None
        manual = bool(schedule and schedule.get("manual_only"))
        expected = latest_slot(schedule, now) if schedule and not manual else None
        enabled = runtime.get("mode") == "active" and schedule is not None
        conditional = name == "mobile-ledger" or manual
        request_pending = setting.get("action") in {"start", "stop"} and setting.get("processed_version") != version
        overdue = None
        if fresh and enabled and not setting.get("paused") and not conditional and expected:
            not_before = stamp(runtime.get("not_before"))
            # A missing record is meaningful only after the controller's hourly grace window.
            if not_before and expected >= not_before and now - expected > timedelta(minutes=70):
                overdue = (not observed_run or stamp(observed_run.get("scheduled_at")) is None or
                           stamp(observed_run["scheduled_at"]) < expected or
                           observed_run.get("status") == "pending" and not observed_run.get("start_time") and
                           stamp(observed_run["scheduled_at"]) <= expected)
        rows.append({"name": name, "title": title, "purpose": purpose,
                     "cadence": ("manual" if manual or name in {"collection-queue", "analysis-queue"} else
                                 "monthly" if schedule and schedule.get("month_days") else
                                 "weekly" if schedule and len(schedule["weekdays"]) < 5 or
                                 not schedule and name in {"data-quality", "iceberg-compaction", "mart-cleanup", "core-cleanup"}
                                 else "daily"),
                     "enabled": enabled, "schedule_verified": fresh, "schedule": schedule,
                     "paused": bool(setting.get("paused")), "control_version": version,
                     "latest": recent, "latest_log": log, "expected_at": expected, "overdue": overdue,
                     "conditional": conditional,
                     "request_pending": request_pending, "control_outcome": setting.get("outcome"),
                     "can_start": fresh and enabled and (manual or expected is not None and
                         stamp(runtime.get("not_before")) is not None and expected >= stamp(runtime["not_before"])) and
                         not request_pending and not (observed_run and observed_run.get("status") in {"pending", "dispatching", "running", "ambiguous"}),
                     "can_stop": bool(not request_pending and recent and (recent.get("status") == "pending" or
                         recent.get("status") in {"running", "dispatching"} and recent.get("can_cancel_execution"))),
                     "stop_note": "僅能停止可確認身分的這次執行，不影響其他工作。備份或結果不確定時不能強制停止。",
                     "unavailable_reason": None if fresh and enabled else "尚無近期已啟用的總控排程證據。"})
    rows.sort(key=lambda row: stamp((row["latest"] or {}).get("scheduled_at")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    rows.append({"name": "monthly-model-review", "title": "每月模型有效性檢查", "purpose": "檢查已成熟預測的模型表現；依模型生命週期規格，尚無總控執行定義。",
                 "cadence": "monthly", "enabled": False, "schedule_verified": False,
                 "latest": None, "can_start": False, "can_stop": False,
                 "paused": False, "control_version": 0,
                 "unavailable_reason": "規格已規劃，總控批次尚未實作；不是舊Cloud Run月度訓練。"})
    return {"items": rows, "observed_at": now, "controller_observed_at": observed,
            "controller_fresh": fresh, "history_days": 7}
