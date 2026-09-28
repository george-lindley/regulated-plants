import os
from datetime import datetime


def _database_last_modified_iso(app) -> str:
    db_path = app.config.get("DATABASE_PATH") or "weeds.db"
    absolute_db_path = db_path if os.path.isabs(db_path) else os.path.abspath(db_path)
    if os.path.exists(absolute_db_path):
        return datetime.fromtimestamp(os.path.getmtime(absolute_db_path)).isoformat()
    return ""


def _date_label(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[:10]
    return parsed.date().isoformat()


def _release_date_kind(entry: dict) -> str:
    return "generated" if entry.get("generated_at") or entry.get("generatedAt") else "refreshed"


def _release_timestamp(entry: dict) -> str:
    return (
        entry.get("generated_at")
        or entry.get("generatedAt")
        or entry.get("last_updated")
        or entry.get("lastUpdated")
        or ""
    )


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_metrics(metrics) -> dict:
    if not isinstance(metrics, dict):
        return {}

    output = {}
    for key in ("taxa", "jurisdictions", "regulation_rows"):
        value = _int_or_none(metrics.get(key))
        if value is not None:
            output[key] = value

    return output


def _normalize_history_entry(entry: dict) -> dict:
    entry = entry if isinstance(entry, dict) else {}
    version = str(entry.get("version") or entry.get("id") or "").strip()
    label = str(entry.get("label") or entry.get("name") or version).strip()
    timestamp = _release_timestamp(entry)
    date_kind = _release_date_kind(entry)
    summary = str(entry.get("summary") or entry.get("notes") or entry.get("description") or "").strip()

    return {
        "version": version,
        "label": label,
        "summary": summary,
        "timestamp": timestamp,
        "date_label": _date_label(timestamp),
        "date_kind": date_kind,
        "metrics": _normalize_metrics(entry.get("metrics")),
        "current": bool(entry.get("current")),
    }


def _normalize_history(history, current_release: dict) -> list:
    if not isinstance(history, list):
        history = []

    normalized = []
    seen_versions = set()
    for entry in history:
        normalized_entry = _normalize_history_entry(entry)
        version = normalized_entry.get("version")
        if not version:
            continue
        normalized.append(normalized_entry)
        seen_versions.add(version)

    current_version = current_release.get("version")
    if current_version and current_version not in seen_versions:
        normalized.insert(
            0,
            {
                "version": current_version,
                "label": current_version,
                "summary": "Current public data release",
                "timestamp": current_release.get("timestamp"),
                "date_label": current_release.get("date_label"),
                "date_kind": current_release.get("date_kind"),
                "metrics": current_release.get("metrics", {}),
                "current": True,
            },
        )
    elif current_version:
        for entry in normalized:
            if entry.get("version") == current_version:
                entry["current"] = True
                break

    return normalized


def build_release_metadata(app) -> dict:
    version = (
        app.config.get("DATA_RELEASE_VERSION")
        or app.config.get("DATA_VERSION")
        or ""
    )
    generated_at = app.config.get("DATA_RELEASE_GENERATED_AT") or ""
    last_updated = app.config.get("DATA_RELEASE_LAST_UPDATED") or ""
    timestamp = generated_at or last_updated or _database_last_modified_iso(app)
    date_kind = "generated" if generated_at else "refreshed"

    release = {
        "version": str(version or "").strip(),
        "timestamp": timestamp,
        "date_label": _date_label(timestamp),
        "date_kind": date_kind,
        "metrics": _normalize_metrics(app.config.get("DATA_RELEASE_METRICS")),
    }

    release["history"] = _normalize_history(app.config.get("DATA_RELEASE_HISTORY"), release)
    if not release["metrics"]:
        for entry in release["history"]:
            if entry.get("current") and entry.get("metrics"):
                release["metrics"] = entry["metrics"]
                break
    release["summary"] = ""
    for entry in release["history"]:
        if entry.get("current") and entry.get("summary"):
            release["summary"] = entry["summary"]
            break
    return release
