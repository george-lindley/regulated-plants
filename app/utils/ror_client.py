import json
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.utils.account_store import email_domain


def _fetch_json(url: str, timeout_seconds: int) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "regulated-plants-app/1.0",
        },
    )
    with urlopen(request, timeout=max(1, int(timeout_seconds or 4))) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_ror_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("https://ror.org/"):
        return raw
    if raw.startswith("http://ror.org/"):
        return raw.replace("http://", "https://", 1)
    return f"https://ror.org/{raw.strip('/')}"


def ror_display_name(record: dict) -> str:
    names = record.get("names") or []
    if isinstance(names, list):
        for preferred_type in ("ror_display", "label"):
            for name in names:
                if preferred_type in (name.get("types") or []) and name.get("value"):
                    return str(name["value"]).strip()
        for name in names:
            if name.get("value"):
                return str(name["value"]).strip()
    return str(record.get("name") or "").strip()


def ror_country(record: dict) -> tuple:
    locations = record.get("locations") or []
    if not isinstance(locations, list) or not locations:
        country = record.get("country") or {}
        return country.get("country_name") or "", country.get("country_code") or ""

    details = (locations[0] or {}).get("geonames_details") or {}
    return details.get("country_name") or "", details.get("country_code") or ""


def ror_domains(record: dict) -> list:
    domains = record.get("domains") or []
    if not isinstance(domains, list):
        return []
    cleaned = []
    for domain in domains:
        value = str(domain or "").strip().lower()
        if value:
            cleaned.append(value)
    return cleaned


def ror_result_payload(record: dict) -> dict:
    country_name, country_code = ror_country(record)
    return {
        "id": normalize_ror_id(record.get("id")),
        "name": ror_display_name(record),
        "country": country_name,
        "country_code": country_code,
        "types": record.get("types") or [],
        "domains": ror_domains(record),
    }


def search_ror_organizations(query: str, base_url: str, timeout_seconds: int, limit: int = 10) -> list:
    term = str(query or "").strip()
    if len(term) < 3:
        return []

    params = urlencode({"query": term})
    url = f"{base_url.rstrip('/')}?{params}"
    payload = _fetch_json(url, timeout_seconds)
    records = payload.get("items") or []
    if not isinstance(records, list):
        return []

    results = []
    for record in records[: max(1, int(limit or 10))]:
        item = ror_result_payload(record)
        if item["id"] and item["name"]:
            results.append(item)
    return results


def fetch_ror_record(ror_id: str, base_url: str, timeout_seconds: int) -> dict:
    normalized = normalize_ror_id(ror_id)
    if not normalized:
        return {}
    path_id = quote(normalized, safe=":/")
    return _fetch_json(f"{base_url.rstrip('/')}/{path_id}", timeout_seconds)


def email_matches_ror_domains(email: str, record: dict) -> bool:
    domain = email_domain(email)
    if not domain:
        return False

    for allowed in ror_domains(record):
        if domain == allowed or domain.endswith(f".{allowed}"):
            return True
    return False
