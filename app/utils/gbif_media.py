"""Display-ready plant photographs sourced from GBIF occurrence media.

The public surface is one function::

    fetch_species_photos(usage_key, base_url=..., timeout_seconds=..., limit=...,
                         cache_ttl_seconds=..., user_agent=...)
        -> list of {"thumbnail_url", "full_url", "creator", "licence", "licence_url",
                    "occurrence_url", "publisher"}

Everything else -- the taxon-key/occurrence-key distinction, the MD5 image-cache URL
scheme, licence normalisation, de-duplication and caching -- is hidden behind it.

Why two GBIF calls' worth of machinery for one image:

  Our database stores ``plants.gbif_usage_key``, which is a GBIF *backbone taxon key*
  (the ``usageKey`` returned by GBIF's species-match API). GBIF's image cache is keyed
  by *occurrence* key -- an individual observation record -- not by taxon. So we first
  ask the occurrence search API which observations of this taxon carry photographs,
  then build a cache URL per photograph:

      https://api.gbif.org/v1/image/cache/<thumbor-args>/occurrence/<occurrenceKey>/media/<md5(identifier)>

  where ``identifier`` is the original media URL from the occurrence record and the MD5
  is hex-encoded. The image cache runs Thumbor, so resizing/cropping is expressed as
  leading path segments (``480x480`` crops to a square, ``fit-in/1600x1600`` letterboxes).
  Serving through the cache rather than hot-linking the source means we get GBIF's CDN,
  consistent sizing, and no traffic sent to individual herbaria or S3 buckets.

Weeds are photogenic in inconsistent ways -- one canonical image rarely exists, and a
herbarium sheet looks nothing like a live plant -- so callers get a small ranked set
rather than a single "best" photo.
"""

import hashlib
import json
import re
import threading
import time
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://api.gbif.org/v1"

# GBIF asks integrators to identify themselves with a contact URL or email in the
# User-Agent, so they can get in touch about problematic traffic instead of simply
# blocking it. Callers should override this with a real address -- see
# GBIF_API_USER_AGENT in app/config.py.
DEFAULT_USER_AGENT = "regulated-plants-app/1.0 (+https://regulatedplants.unu.edu)"

# Square crop for the grid tiles (2x a ~240px tile), letterboxed for the lightbox.
THUMBNAIL_TRANSFORM = "480x480"
FULL_TRANSFORM = "fit-in/1600x1600"

# How many occurrences to inspect per GBIF call. Occurrence records are fat
# (~7KB each), so this trades payload for the diversity we filter down from.
# Keep it at 20: measured against api.gbif.org, limit=20 returns in a steady
# ~0.8s while limit=40 is erratic (0.9s to 36s on the same query), which would
# blow the request timeout for no extra benefit.
_SEARCH_PAGE_SIZE = 20

# Below this, fall back to a second unfiltered search that also allows
# herbarium specimens rather than showing the user almost nothing.
_MIN_PHOTOS_BEFORE_FALLBACK = 3

_CACHE_MAX_ENTRIES = 2048
# Backbone taxonomy moves on the order of months; hold synonym resolutions a week.
_TAXON_CACHE_TTL_SECONDS = 604800
# Empty results are re-checked sooner than populated ones: "no photos yet" is the
# state most likely to change, and it is also what a transient GBIF outage looks like.
_EMPTY_RESULT_TTL_SECONDS = 900

_CC_PATTERN = re.compile(
    r"creativecommons\.org/(licenses|publicdomain)/([a-z-]+)/(\d(?:\.\d)?)",
    re.IGNORECASE,
)

_PUBLIC_DOMAIN_LABELS = {
    "zero": "CC0",
    "mark": "Public Domain Mark",
}


# ----------------------------
# HTTP
# ----------------------------
class _Endpoint(NamedTuple):
    """Where and how we talk to GBIF. Grouped so it threads as one argument."""

    base_url: str
    timeout_seconds: int
    user_agent: str


def _fetch_json(endpoint: _Endpoint, path: str) -> dict:
    request = Request(
        f"{endpoint.base_url}{path}",
        headers={
            "Accept": "application/json",
            "User-Agent": endpoint.user_agent or DEFAULT_USER_AGENT,
        },
    )
    with urlopen(request, timeout=max(1, int(endpoint.timeout_seconds or 8))) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_accepted_key(endpoint: _Endpoint, usage_key: int) -> int:
    """Follow a synonym key to the taxon GBIF currently accepts.

    GBIF's backbone periodically reclassifies a name as a synonym of another
    taxon. The old key keeps resolving -- nothing 404s -- but occurrences pile up
    under the *accepted* key, so querying the synonym silently returns a fraction
    of the images. Measured on our own data: ``Cardaria draba`` (3052311) has 22
    occurrences with photos, while the accepted ``Lepidium draba`` (5376961) has
    22,689.

    Resolving here rather than in the database keeps the stored key stable for
    citation and keeps the gallery correct even as the backbone shifts underneath
    us. Costs one extra ~0.2s call on a cold lookup, then it is cached.
    """
    cache_key = ("accepted", int(usage_key))
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    resolved = int(usage_key)
    try:
        record = _fetch_json(endpoint, f"/species/{int(usage_key)}")
        status = str(record.get("taxonomicStatus") or "").upper()
        accepted = record.get("acceptedKey")
        if accepted and status.endswith("SYNONYM"):
            resolved = int(accepted)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
        pass  # Fall back to the stored key; a partial gallery beats none.

    _cache.put(cache_key, resolved, _TAXON_CACHE_TTL_SECONDS)
    return resolved


def _search_occurrences(endpoint: _Endpoint, usage_key: int, human_only: bool) -> list:
    params = {
        "taxonKey": int(usage_key),
        "mediaType": "StillImage",
        "limit": _SEARCH_PAGE_SIZE,
    }
    if human_only:
        # Living plants in situ. Without this the first page skews to herbarium
        # sheets, which are useful to a taxonomist and useless to someone trying
        # to recognise a weed in a field.
        params["basisOfRecord"] = "HUMAN_OBSERVATION"

    payload = _fetch_json(endpoint, f"/occurrence/search?{urlencode(params)}")
    results = payload.get("results")
    return results if isinstance(results, list) else []


# ----------------------------
# Normalisation
# ----------------------------
def _licence(*candidates) -> tuple:
    """Return ``(label, url)`` for the first recognisable Creative Commons licence.

    GBIF licence values are mostly CC URLs but some publishers put free text there
    (``"Reshma Tadvi (cc-by-sa)"``). Anything we cannot resolve to a specific CC
    licence is treated as unlicensed and the photo is dropped -- we would not be
    able to attribute it correctly.
    """
    for candidate in candidates:
        match = _CC_PATTERN.search(str(candidate or ""))
        if not match:
            continue

        family, code, version = match.group(1).lower(), match.group(2).lower(), match.group(3)
        if family == "publicdomain":
            label = _PUBLIC_DOMAIN_LABELS.get(code)
            if not label:
                continue
            return f"{label} {version}", f"https://creativecommons.org/publicdomain/{code}/{version}/"

        return f"CC {code.upper()} {version}", f"https://creativecommons.org/licenses/{code}/{version}/"

    return "", ""


def _image_url(base_url: str, occurrence_key, identifier: str, transform: str) -> str:
    digest = hashlib.md5(identifier.encode("utf-8")).hexdigest()
    return f"{base_url.rstrip('/')}/image/cache/{transform}/occurrence/{occurrence_key}/media/{digest}"


def _photo_from_occurrence(record: dict, base_url: str) -> dict:
    """Pick at most one still image from an occurrence, normalised for display.

    One photo per occurrence on purpose: an iNaturalist observation often carries
    five shots of the same individual from the same angle, which would fill the
    gallery with near-duplicates.
    """
    occurrence_key = record.get("key")
    if not occurrence_key:
        return {}

    for media in record.get("media") or []:
        if not isinstance(media, dict) or media.get("type") != "StillImage":
            continue

        identifier = str(media.get("identifier") or "").strip()
        if not identifier.startswith(("http://", "https://")):
            continue

        label, licence_url = _licence(media.get("license"), record.get("license"))
        if not label:
            continue

        creator = str(media.get("rightsHolder") or media.get("creator") or "").strip()
        return {
            "thumbnail_url": _image_url(base_url, occurrence_key, identifier, THUMBNAIL_TRANSFORM),
            "full_url": _image_url(base_url, occurrence_key, identifier, FULL_TRANSFORM),
            "creator": creator or "Unknown",
            "licence": label,
            "licence_url": licence_url,
            "publisher": str(media.get("publisher") or "").strip(),
            "occurrence_url": f"https://www.gbif.org/occurrence/{occurrence_key}",
        }

    return {}


def _collect_photos(records: list, base_url: str, limit: int, seen_creators: set) -> list:
    """De-duplicate by photographer so the gallery shows a range of specimens.

    A single prolific recorder can own most of the first page of results for a
    species; without this the "gallery" is one person's back garden.
    """
    photos = []
    for record in records:
        if len(photos) >= limit:
            break
        if not isinstance(record, dict):
            continue

        photo = _photo_from_occurrence(record, base_url)
        if not photo:
            continue

        creator_key = photo["creator"].casefold()
        if creator_key in seen_creators:
            continue

        seen_creators.add(creator_key)
        photos.append(photo)
    return photos


# ----------------------------
# Cache
# ----------------------------
class _PhotoCache:
    """Tiny in-process TTL cache.

    Each gunicorn worker keeps its own copy, which is fine: entries are cheap,
    identical across workers, and the images themselves are already served from
    GBIF's CDN. This only saves the ~0.9s occurrence-search round trip.
    """

    def __init__(self):
        self._entries = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() >= expires_at:
                self._entries.pop(key, None)
                return None
            return value

    def put(self, key, value, ttl_seconds: int):
        if ttl_seconds <= 0:
            return
        with self._lock:
            if len(self._entries) >= _CACHE_MAX_ENTRIES:
                # Cheap eviction: drop whatever expires soonest.
                oldest = min(self._entries, key=lambda k: self._entries[k][0])
                self._entries.pop(oldest, None)
            self._entries[key] = (time.time() + ttl_seconds, value)

    def clear(self):
        with self._lock:
            self._entries.clear()


_cache = _PhotoCache()


# ----------------------------
# Public interface
# ----------------------------
def fetch_species_photos(
    usage_key,
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: int = 8,
    limit: int = 6,
    cache_ttl_seconds: int = 86400,
    user_agent: str = DEFAULT_USER_AGENT,
) -> list:
    """Return up to ``limit`` display-ready photographs for a GBIF taxon key.

    Never raises: a GBIF outage, timeout or malformed payload yields an empty list,
    because a missing gallery must not break the species page.
    """
    try:
        key = int(usage_key)
    except (TypeError, ValueError):
        return []
    if key <= 0:
        return []

    limit = max(1, min(int(limit or 6), 12))
    cache_key = (key, limit)

    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    endpoint = _Endpoint(
        base_url=(base_url or DEFAULT_BASE_URL).rstrip("/"),
        timeout_seconds=timeout_seconds,
        user_agent=user_agent or DEFAULT_USER_AGENT,
    )
    search_key = _resolve_accepted_key(endpoint, key)
    seen_creators = set()
    photos = []

    for human_only in (True, False):
        try:
            records = _search_occurrences(endpoint, search_key, human_only)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            # Includes json.JSONDecodeError (a ValueError) and socket timeouts.
            records = []

        photos.extend(_collect_photos(records, endpoint.base_url, limit - len(photos), seen_creators))
        if len(photos) >= _MIN_PHOTOS_BEFORE_FALLBACK:
            break

    ttl = cache_ttl_seconds if photos else min(cache_ttl_seconds, _EMPTY_RESULT_TTL_SECONDS)
    _cache.put(cache_key, photos, ttl)
    return photos


def clear_photo_cache():
    """Drop cached lookups. Exposed for tests and for data-release swaps."""
    _cache.clear()
