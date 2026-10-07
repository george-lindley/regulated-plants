# app/views.py
import gzip
import json
import os
import re
import requests as http_requests
from flask import Blueprint, render_template, jsonify, current_app, request, flash, url_for, redirect, send_from_directory, abort
from werkzeug.utils import safe_join

from app import limiter, recaptcha
from app.auth_helpers import account_logged_in
from app.utils.state_database import StateDatabase
from app.utils.species_database import SpeciesDatabase
from app.utils.species_slug import species_slug
from app.utils.generate_blog import BlogGenerator
from app.utils.email_sender import send_email
from app.utils.gbif_media import fetch_species_photos
from app.utils.release_metadata import build_release_metadata

# Blueprints
home = Blueprint("home", __name__)
species = Blueprint("species", __name__, url_prefix="/species")
blog = Blueprint("blog", __name__, url_prefix="/blog")
method = Blueprint("method", __name__, url_prefix="/method")
api_page = Blueprint("api_page", __name__, url_prefix="/api")
about = Blueprint("about", __name__, url_prefix="/about")

# Blog generator
blog_generator = BlogGenerator()


# ----------------------------
# Helpers
# ----------------------------
def _get_state_db() -> StateDatabase:
    db = current_app.extensions.get("state_db")
    if db is None:
        db = StateDatabase(
            db_path=current_app.config.get("DATABASE_PATH", "weeds.db"),
            geojson_dir=current_app.config.get("GEOJSON_DIR"),
        )
        current_app.extensions["state_db"] = db
    return db


def _get_species_db() -> SpeciesDatabase:
    db = current_app.extensions.get("species_db")
    if db is None:
        db = SpeciesDatabase(
            db_path=current_app.config.get("DATABASE_PATH", "weeds.db"),
            geojson_dir=current_app.config.get("GEOJSON_DIR"),
        )
        current_app.extensions["species_db"] = db
    return db


def _release_metadata() -> dict:
    return build_release_metadata(current_app)


def _release_metrics() -> dict:
    metrics = _release_metadata().get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _release_contact_label() -> str:
    release = _release_metadata()
    version = release.get("version") or "current release"
    date_label = release.get("date_label")
    if date_label:
        return f"{version} ({date_label})"
    return version


def _enterprise_contact_message() -> str:
    return (
        "I would like to request Enterprise access for automated plant compliance checks.\n\n"
        "Organization:\n"
        "Commercial workflow or platform:\n"
        "Intended use case:\n"
        "Expected request volume:"
    )


def _data_correction_contact_message() -> str:
    return (
        f"Data release: {_release_contact_label()}\n\n"
        "Plant or jurisdiction:\n"
        "Current record:\n"
        "Correction needed:\n"
        "Source or reference URL:"
    )


def _bool_arg(name: str, default: bool = True) -> bool:
    v = request.args.get(name, str(default)).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _toggle_params():
    """
    3-toggle system (all ON by default):
      includeRegion
      includeNational
      includeInternational
    """
    include_region = _bool_arg("includeRegion", True)
    include_national = _bool_arg("includeNational", True)
    include_international = _bool_arg("includeInternational", True)
    return include_region, include_national, include_international


# ----------------------------
# Home routes
# ----------------------------
@home.route("/")
def index():
    metrics_enabled = str(current_app.config.get("OOZR_METRICS_ENABLED", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return render_template(
        "home.html",
        geojson_path=current_app.config.get("GEOJSON_URL_PATH", "/data/geojson/"),
        data_version=current_app.config.get("DATA_VERSION", ""),
        oozr_base_url=current_app.config.get("OOZR_BASE_URL", ""),
        oozr_project_slug=current_app.config.get("OOZR_PROJECT_SLUG", "regulatedplants"),
        oozr_metrics_enabled=metrics_enabled,
    )


@home.route("/privacy")
def privacy():
    return render_template("privacy.html")


@home.route("/robots.txt")
def robots_txt():
    return current_app.send_static_file("robots.txt")


@home.route("/sitemap.xml")
def sitemap_xml():
    """Every public page, including one URL per species (referenced by robots.txt)."""
    site_url = current_app.config["SITE_URL"]
    pages = [
        url_for("home.index"),
        url_for("species.index"),
        url_for("blog.index"),
        url_for("method.index"),
        url_for("about.index"),
        url_for("api_page.api_index"),
    ]
    pages += [url_for("blog.post", slug=post["slug"]) for post in blog_generator.blog_posts]
    pages += [url_for("species.detail", slug=slug) for slug in _get_species_db().get_all_slugs()]

    response = current_app.response_class(
        render_template("sitemap.xml", urls=[f"{site_url}{path}" for path in pages]),
        mimetype="application/xml",
    )
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@home.route("/api/region-weed-counts")
def region_weed_counts():
    """
    Returns map rows keyed by stable geo_region_id.
    Used to colour the map and drive tooltip provenance.
    """
    include_region, include_national, include_international = _toggle_params()
    counts = _get_state_db().get_region_weed_counts(
        include_region=include_region,
        include_national=include_national,
        include_international=include_international,
    )
    return jsonify(counts)


@home.route("/api/region")
def region_weeds():
    """
    Returns weeds for a specific mapped geo region.
    Called by map click.

    Query args:
      geo_region_id=<stable map region id>
      includeRegion/includeNational/includeInternational
    """
    geo_region_id = request.args.get("geo_region_id", "").strip()
    if not geo_region_id:
        return jsonify({"error": "geo_region_id is required"}), 400

    include_region, include_national, include_international = _toggle_params()
    payload = _get_state_db().get_weeds_for_geo_region(
        geo_region_id=geo_region_id,
        include_region=include_region,
        include_national=include_national,
        include_international=include_international,
    )
    if not payload.get("geo_region"):
        return jsonify({"error": "geo_region_id not found"}), 404

    authenticated = account_logged_in()
    sample_limit = max(0, int(current_app.config.get("AUTH_ANONYMOUS_SAMPLE_LIMIT", 5)))
    weeds = payload.get("weeds") or []
    total_count = len(weeds)
    if not authenticated:
        payload["weeds"] = weeds[:sample_limit]

    payload["authenticated"] = authenticated
    payload["sample_limit"] = sample_limit
    payload["total_count"] = total_count
    payload["is_sample"] = (not authenticated) and total_count > len(payload.get("weeds") or [])

    return jsonify(payload)


@home.route("/api/geojson-files")
def geojson_files():
    """
    Return a list of GeoJSON filenames in static/data/geographic.
    map.js will call this to know which files to load.
    """
    try:
        geo_dir = current_app.config.get("GEOJSON_DIR")

        files = []
        if geo_dir and os.path.isdir(geo_dir):
            for fname in os.listdir(geo_dir):
                if fname.lower().endswith(".geojson"):
                    files.append(fname)

        files.sort()
        return jsonify(files)
    except Exception as e:
        current_app.logger.error(f"Error listing geojson files: {e}")
        return jsonify({"error": "Failed to list geojson files"}), 500


@home.route("/data/geojson/<path:filename>")
def geojson_file(filename: str):
    geo_dir = current_app.config.get("GEOJSON_DIR")
    if not geo_dir:
        return jsonify({"error": "GeoJSON directory not configured"}), 500
    file_path = safe_join(geo_dir, filename)
    if not file_path or not os.path.isfile(file_path):
        abort(404)

    data_version = str(current_app.config.get("DATA_VERSION") or "").strip()
    request_version = request.args.get("v", "").strip()
    has_current_version = bool(data_version and request_version == data_version)
    max_age = int(current_app.config.get("GEOJSON_CACHE_MAX_AGE_SECONDS", 31536000))

    accepts_gzip = "gzip" in request.headers.get("Accept-Encoding", "").lower()
    if has_current_version and accepts_gzip:
        with open(file_path, "rb") as f:
            compressed = gzip.compress(f.read(), compresslevel=6)
        response = current_app.response_class(
            compressed,
            mimetype="application/geo+json",
        )
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Vary"] = "Accept-Encoding"
        response.headers["Cache-Control"] = f"public, max-age={max_age}, immutable"
        return response

    response = send_from_directory(
        geo_dir,
        filename,
        max_age=max_age if has_current_version else 0,
    )
    response.headers["Vary"] = "Accept-Encoding"
    if has_current_version:
        response.headers["Cache-Control"] = f"public, max-age={max_age}, immutable"
    else:
        response.headers["Cache-Control"] = "no-cache"
    return response


@home.route("/api/home-highlights")
def home_highlights():
    """
    Homepage highlight cards.
    """
    try:
        release = _release_metadata()
        release_metrics = _release_metrics()
        has_release_counts = bool(
            release_metrics.get("taxa") is not None
            and release_metrics.get("jurisdictions") is not None
        )
        metrics = _get_state_db().get_highlight_metrics(include_counts=not has_release_counts)

        last_updated = release.get("timestamp") or None

        override_country = current_app.config.get("LATEST_COUNTRY_NAME")
        if override_country:
            latest_country_name = override_country
            latest_country_region = override_country  # use country as link target
            latest_country_regions = metrics.get("latest_country_regions", 0) or 1
        else:
            latest_country_name = metrics.get("latest_country")
            latest_country_region = metrics.get("latest_country_region") or latest_country_name
            latest_country_regions = metrics.get("latest_country_regions", 0) or 1

        return jsonify(
            {
                "stats": {
                    "species": release_metrics.get("taxa", metrics.get("species_count", 0)),
                    "jurisdictions": release_metrics.get(
                        "jurisdictions",
                        metrics.get("jurisdiction_count", 0),
                    ),
                },
                "release": {
                    "version": release.get("version"),
                    "generatedAt": release.get("timestamp"),
                    "dateLabel": release.get("date_label"),
                    "dateKind": release.get("date_kind"),
                    "summary": release.get("summary"),
                    "metricsSource": "manifest" if has_release_counts else "database",
                },
                "latestCountry": {
                    "name": latest_country_name,
                    "jurisdictions": latest_country_regions,
                    # home_highlights.js expects "stateName" (we'll supply region)
                    "stateName": latest_country_region,
                },
                "topSpecies": metrics.get("top_species"),
                "topJurisdiction": metrics.get("top_jurisdiction"),
                "lastUpdated": last_updated,
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error building home highlights: {e}")
        return jsonify({"error": "Failed to load highlights"}), 500


# ----------------------------
# Species routes
# ----------------------------
@species.route("/")
def index():
    # Legacy deep links (?species_id= / ?name=) move permanently to the slug URL.
    # An inexact ?name= falls through to the page, whose JS runs a fuzzy search.
    species_id = request.args.get("species_id", "").strip()
    name = request.args.get("name", "").strip()
    found = None
    if species_id:
        found = _get_species_db().get_species_by_id(species_id, current_only=False)
    elif name:
        found = _get_species_db().get_species_by_slug(species_slug(name))
    if found:
        return redirect(url_for("species.detail", slug=found["slug"]), code=301)
    return render_template("species.html", species=None)


@species.route("/<slug>")
def detail(slug: str):
    """Permanent species page. These URLs are published by partners (CABI),
    so they must keep resolving across data releases."""
    normalized = species_slug(slug)
    if not normalized:
        return redirect(url_for("species.index"), code=301)
    if normalized != slug:
        return redirect(url_for("species.detail", slug=normalized), code=301)

    species_db = _get_species_db()
    found = species_db.get_species_by_slug(slug)
    if not found:
        renamed_to = species_db.get_slug_redirect(slug)
        if renamed_to:
            return redirect(url_for("species.detail", slug=renamed_to), code=301)
        return render_template("species.html", species=None, missing_slug=slug), 404

    canonical_url = f"{current_app.config['SITE_URL']}{url_for('species.detail', slug=slug)}"
    synonyms = [name.strip() for name in (found.get("synonyms") or "").split(",") if name.strip()]
    return render_template(
        "species.html",
        species=found,
        canonical_url=canonical_url,
        synonyms_preview=", ".join(synonyms[:3]),
        traits={
            "Life Form": _format_trait(found.get("lifeform_final")),
            "Lifespan": _format_trait(found.get("lifespan_final")),
            "Habitat": _format_trait(found.get("habitat_final")),
            "Woodiness": _format_trait(found.get("woodiness_final")),
        },
        jurisdiction_count=_jurisdiction_count(species_db.get_states_by_species_id(found["species_id"])),
        related_species=species_db.get_related_species(found["species_id"], found["canonical_name"]),
        structured_data=_species_structured_data(found, synonyms, canonical_url),
    )


def _format_trait(value) -> str:
    """Server-side twin of formatTraitValue() in species_search.js."""
    raw = str(value or "").strip()
    if not raw:
        return "Not Available"
    if raw == raw.upper() and len(raw) <= 4:
        return raw
    return re.sub(r"(^|[\s\-/,(])([a-z])", lambda m: m.group(1) + m.group(2).upper(), raw.lower())


def _species_structured_data(found: dict, synonyms: list, canonical_url: str) -> dict:
    """schema.org Taxon (Bioschemas profile) so search engines and biodiversity
    tools can read the page as a species record."""
    data = {
        "@context": "https://schema.org",
        "@type": "Taxon",
        "http://purl.org/dc/terms/conformsTo": {
            "@id": "https://bioschemas.org/profiles/Taxon/1.0-RELEASE",
            "@type": "CreativeWork",
        },
        "@id": canonical_url,
        "url": canonical_url,
        "name": found["canonical_name"],
    }
    if found.get("taxon_level"):
        data["taxonRank"] = found["taxon_level"]
    # Hybrids currently inherit their parent's synonyms, common name and GBIF key
    # in the data, so none of those describe the hybrid itself.
    if found.get("taxon_level") == "hybrid":
        return data
    alternate_names = synonyms[:]
    if found.get("common_name") and found["common_name"] != found["canonical_name"]:
        alternate_names.insert(0, found["common_name"])
    if alternate_names:
        data["alternateName"] = alternate_names
    # sameAs asserts identity, so a COL ID matched onto a parent or the genus is left out.
    gbif_key = found.get("taxon_id") if found.get("taxon_match") in {"exact", "variant"} else None
    if gbif_key:
        data["sameAs"] = f"https://www.gbif.org/species/{gbif_key}"
        data["identifier"] = {
            "@type": "PropertyValue",
            "propertyID": "GBIF",
            "value": str(gbif_key),
        }
    return data


@species.route("/api/search")
def search_species():
    query = request.args.get("q", "")
    results = _get_species_db().search_weeds(query)
    return jsonify(results)


@species.route("/api/by-species-id/<species_id>")
def species_by_id(species_id: str):
    result = _get_species_db().get_species_by_id(species_id)
    if not result:
        return jsonify({"error": "Species not found"}), 404
    return jsonify(result)


@species.route("/api/photos/by-species-id/<species_id>")
@limiter.limit("240 per hour")
def species_photos_by_species_id(species_id: str):
    """Photographs of a species, sourced from GBIF occurrence media via its GBIF
    Catalogue of Life taxon ID.

    Public on purpose: unlike regulation detail, these are third-party CC-licensed
    images that carry no dataset value of ours. Hybrids and genus-level matches show
    their parent's or genus's photos, which is the closest honest answer.
    """
    if not current_app.config.get("GBIF_PHOTOS_ENABLED", True):
        return jsonify({"photos": []})

    keys = _get_species_db().get_gbif_keys(species_id)
    if not keys:
        return jsonify({"photos": []}), 404

    photos = fetch_species_photos(
        keys.get("taxon_id"),
        checklist_key=current_app.config.get("GBIF_TAXON_CHECKLIST_KEY"),
        base_url=current_app.config.get("GBIF_API_BASE_URL"),
        timeout_seconds=current_app.config.get("GBIF_API_TIMEOUT_SECONDS", 6),
        limit=current_app.config.get("GBIF_PHOTO_LIMIT", 6),
        cache_ttl_seconds=current_app.config.get("GBIF_PHOTO_CACHE_TTL_SECONDS", 86400),
        user_agent=current_app.config.get("GBIF_API_USER_AGENT"),
    )

    response = jsonify({"photos": photos})
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


def _jurisdiction_count(regulations_by_group: dict) -> int:
    if not isinstance(regulations_by_group, dict):
        return 0
    return sum(
        len(jurisdictions)
        for jurisdictions in regulations_by_group.values()
        if isinstance(jurisdictions, list)
    )


def _species_regulation_payload(regulations_by_group: dict):
    jurisdiction_count = _jurisdiction_count(regulations_by_group)
    authenticated = account_logged_in()
    payload = {
        "authenticated": authenticated,
        "jurisdiction_count": jurisdiction_count,
    }
    if authenticated:
        payload["regulations_by_country"] = regulations_by_group
    return jsonify(payload)


@species.route("/api/weed-states/by-species-id/<species_id>")
def weed_states_by_species_id(species_id: str):
    """
    Returns regulations for one stable species row. GBIF usage keys are not
    unique in the v1.1 data, so species search uses species_id for lookups.
    """
    try:
        regulations_by_group = _get_species_db().get_states_by_species_id(species_id)
        return _species_regulation_payload(regulations_by_group)
    except Exception as e:
        current_app.logger.error(f"Error fetching states for species ID {species_id}: {str(e)}")
        return jsonify({"error": "Failed to fetch states"}), 500


# ----------------------------
# Blog routes
# ----------------------------
@blog.route("/")
def index():
    tag = request.args.get("tag")
    posts = blog_generator.get_posts_by_tag(tag) if tag else blog_generator.blog_posts

    return render_template(
        "blog.html",
        blog_posts=posts,
        all_tags=blog_generator.tags,
        current_tag=tag,
        title="Blog" if not tag else f"Blog - {tag}",
        description="Latest updates about regulated weeds",
    )


@blog.route("/<slug>")
def post(slug):
    post = blog_generator.get_post_by_slug(slug)
    if post:
        latest_posts = [p for p in blog_generator.blog_posts if p["slug"] != slug][:5]
        return render_template("blog_post.html", post=post, title=post["title"], latest_posts=latest_posts)
    return "Post not found", 404


# ----------------------------
# Method routes
# ----------------------------
@method.route("/")
def index():
    try:
        sources = _get_state_db().get_method_sources()
    except Exception as e:
        current_app.logger.error(f"Error loading methodology sources from database: {e}")
        sources = []

    source_groups = _group_sources_by_country(sources)
    return render_template(
        "method.html",
        source_groups=source_groups,
        source_count=sum(len(group["items"]) for group in source_groups),
    )


def _group_sources_by_country(sources: list) -> list:
    """Distinct sources per country for the methodology index.

    The query returns one row per jurisdiction, but one national list often covers
    every state or province (South Africa: 16 provinces, one source). Rows sharing
    an authority and source URL are merged into one source that lists what it covers.
    """
    groups = {}
    for row in sources:
        country = row.get("country") or "Other"
        key = (row.get("authority") or "", row.get("source_url") or "") if row.get("source_url") else id(row)
        merged = groups.setdefault(country, {}).setdefault(
            key, {"authority": row.get("authority"), "source_url": row.get("source_url"), "covers": [], "years": []}
        )
        if row.get("name") and row["name"] not in merged["covers"]:
            merged["covers"].append(row["name"])
        if str(row.get("updated", "")).isdigit():
            merged["years"].append(str(row["updated"]))

    result = []
    for country, by_source in groups.items():
        items = []
        for merged in by_source.values():
            items.append({
                "name": ", ".join(merged["covers"]),
                "authority": merged["authority"],
                "source_url": merged["source_url"],
                "updated": max(merged["years"]) if merged["years"] else "Unknown",
            })
        years = [item["updated"] for item in items if item["updated"].isdigit()]
        result.append({"country": country, "items": items, "latest_year": max(years) if years else None})
    return sorted(result, key=lambda group: group["country"])


# ----------------------------
# API page routes
# ----------------------------
def _api_demo_rate_limit() -> str:
    return "30 per hour"


def _data_service_base_url() -> str:
    return (current_app.config.get("DATA_REMOTE_BASE_URL") or "").rstrip("/")


def _openapi_servers():
    base_url = _data_service_base_url() or (current_app.config.get("BASE_URL") or "").rstrip("/")
    if not base_url:
        return []
    return [
        {
            "url": base_url,
            "description": "Production API",
        }
    ]


def _data_service_token() -> str:
    return current_app.config.get("DATA_REMOTE_TOKEN") or ""


def _api_demo_timeout_seconds() -> int:
    # The normal data sync timeout can be longer; the public demo should fail quickly.
    remote_timeout = current_app.config.get("DATA_REMOTE_TIMEOUT_SECONDS", 8)
    return max(1, min(int(remote_timeout or 8), 8))


def _api_demo_string(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _format_count(value) -> str:
    try:
        return f"{int(value or 0):,}"
    except (TypeError, ValueError):
        return "0"


def _api_release_metrics() -> dict:
    release = _release_metadata()
    release_metrics = _release_metrics()

    missing_counts = [
        key
        for key in ("taxa", "jurisdictions", "regulation_rows")
        if release_metrics.get(key) is None
    ]
    database_metrics = {}
    if missing_counts:
        try:
            database_metrics = _get_state_db().get_highlight_metrics()
        except Exception as exc:
            current_app.logger.warning("Unable to load API release metrics: %s", exc)
            database_metrics = {}

    return {
        "version": release.get("version"),
        "date_label": release.get("date_label"),
        "date_kind": release.get("date_kind"),
        "species": _format_count(
            release_metrics.get("taxa", database_metrics.get("species_count"))
        ),
        "jurisdictions": _format_count(
            release_metrics.get("jurisdictions", database_metrics.get("jurisdiction_count"))
        ),
        "regulations": _format_count(
            release_metrics.get("regulation_rows", database_metrics.get("regulation_count"))
        ),
        "source": "manifest" if not missing_counts else "database_fallback",
    }


def _api_demo_payload():
    incoming = request.get_json(silent=True) or {}
    if not isinstance(incoming, dict):
        incoming = {}

    ship_to = incoming.get("ship_to")
    if not isinstance(ship_to, dict):
        ship_to = {}

    plant_query = _api_demo_string(incoming.get("plant_query") or incoming.get("plant"), 200)
    country = _api_demo_string(ship_to.get("country") or incoming.get("country"), 64)
    region = _api_demo_string(
        ship_to.get("region") or incoming.get("region") or incoming.get("state"),
        64,
    )
    return plant_query, country, region


@api_page.route("")
def api_index():
    return render_template(
        "api.html",
        api_service_base_url=_data_service_base_url(),
        api_release_metrics=_api_release_metrics(),
    )


@api_page.route("/demo/regulatory-check", methods=["POST"])
@limiter.limit(_api_demo_rate_limit)
def demo_regulatory_check():
    plant_query, country, region = _api_demo_payload()
    if not plant_query:
        return jsonify({"error": "plant_query is required"}), 400
    if not country:
        return jsonify({"error": "ship_to.country is required"}), 400

    base_url = _data_service_base_url()
    if not base_url:
        return jsonify(
            {
                "error": (
                    "Data service base URL is not configured. Set DATA_REMOTE_BASE_URL "
                    "to the regulated_plants_data service URL."
                )
            }
        ), 500

    ship_to = {"country": country}
    if region:
        ship_to["region"] = region

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    demo_token = _data_service_token()
    if demo_token:
        headers["Authorization"] = f"Bearer {demo_token}"

    upstream_url = f"{base_url}/v1/regulatory-check"
    try:
        upstream_response = http_requests.post(
            upstream_url,
            json={"plant_query": plant_query, "ship_to": ship_to},
            headers=headers,
            timeout=_api_demo_timeout_seconds(),
        )
    except http_requests.RequestException as exc:
        current_app.logger.warning("API demo request failed: %s", exc)
        return jsonify({"error": "The API service is not reachable right now."}), 502

    try:
        payload = upstream_response.json()
    except ValueError:
        current_app.logger.warning(
            "API demo received non-JSON response from %s with status %s",
            upstream_url,
            upstream_response.status_code,
        )
        return jsonify({"error": "The API service returned an unreadable response."}), 502

    if upstream_response.status_code in {401, 403}:
        return jsonify(
            {
                "error": "Demo API access is not configured.",
                "upstream_status": upstream_response.status_code,
            }
        ), 502
    if upstream_response.status_code >= 500:
        return jsonify(
            {
                "error": "The API service returned an upstream error.",
                "upstream_status": upstream_response.status_code,
            }
        ), 502
    return jsonify(payload), upstream_response.status_code


@api_page.route("/docs")
def docs():
    return render_template("api_docs.html")


@api_page.route("/terms")
def terms():
    return render_template("api_terms.html")


@api_page.route("/openapi.json")
def openapi_json():
    spec_path = current_app.config.get("API_OPENAPI_PATH")
    if not spec_path:
        return jsonify({"error": "OpenAPI document is not configured"}), 500
    if not os.path.isabs(spec_path):
        spec_path = os.path.abspath(spec_path)
    if not os.path.isfile(spec_path):
        return jsonify({"error": "OpenAPI document not found"}), 404
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = json.load(f)

    servers = _openapi_servers()
    if servers:
        spec["servers"] = servers
    return jsonify(spec)


# ----------------------------
# About routes
# ----------------------------
@about.route("/")
def index():
    contact_subject = (request.args.get("subject") or "general").strip()
    allowed_subjects = {"general", "data", "collaboration", "api_access", "other"}
    if contact_subject not in allowed_subjects:
        contact_subject = "general"

    contact_message = ""
    contact_form_defaults = {
        "api_access": _enterprise_contact_message(),
        "data": _data_correction_contact_message(),
    }
    if contact_subject == "api_access":
        contact_message = contact_form_defaults["api_access"]
    elif contact_subject == "data":
        contact_message = contact_form_defaults["data"]

    return render_template(
        "about.html",
        contact_subject=contact_subject,
        contact_message=contact_message,
        contact_form_defaults=contact_form_defaults,
    )


@about.route("/contact", methods=["POST"])
@limiter.limit("5 per hour")
def contact():
    # Honeypot bot field
    if request.form.get("website"):
        return redirect(url_for("about.index"))

    # reCAPTCHA
    if not recaptcha.verify():
        flash("Please complete the reCAPTCHA verification.", "error")
        return redirect(url_for("about.index"))

    name = request.form.get("name")
    email = request.form.get("email")
    subject_type = request.form.get("subject")
    message_text = request.form.get("message")

    if not all([name, email, subject_type, message_text]):
        flash("All fields are required", "error")
        return redirect(url_for("about.index"))

    subject_map = {
        "general": "General Inquiry",
        "data": "Data Correction Request",
        "collaboration": "Collaboration Request",
        "api_access": "Enterprise Access Request",
        "other": "Other Inquiry",
    }
    email_subject = f"[Regulated Plants] {subject_map.get(subject_type, 'Contact Form')}"

    email_body = f"""
You have received a new message from the Regulated Plants contact form:

Name: {name}
Email: {email}
Subject: {subject_map.get(subject_type, 'Not specified')}

Message:
{message_text}
""".strip()

    try:
        send_email(
            current_app.config,
            email_subject,
            current_app.config.get("CONTACT_EMAIL"),
            email_body,
            reply_to=email,
        )
        flash("Thank you for your message! We will get back to you soon.", "success")
    except Exception as e:
        current_app.logger.error(f"Error sending email: {str(e)}")
        flash("There was an issue sending your message. Please try again later.", "error")

    return redirect(url_for("about.index"))


# ----------------------------
# Debug route
# ----------------------------
@home.route("/debug/table-check")
def check_tables():
    if current_app.config.get("DEBUG") is not True:
        abort(404)

    conn = _get_state_db().get_connection()
    try:
        expected = ["plants", "jurisdictions", "regulations"]
        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name IN ('plants', 'jurisdictions', 'regulations')
            ORDER BY name
            """
        ).fetchall()

        available = {row["name"] for row in tables}
        counts = {}
        for table_name in expected:
            if table_name not in available:
                counts[table_name] = 0
                continue
            row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
            counts[table_name] = row["count"] if row else 0

        return jsonify({"tables_found": [dict(t) for t in tables], "row_counts": counts})
    finally:
        conn.close()


@home.route("/api/data-status")
def data_status():
    if current_app.config.get("DEBUG") is not True:
        abort(404)

    db_path = current_app.config.get("DATABASE_PATH")
    geojson_dir = current_app.config.get("GEOJSON_DIR")
    manifest_path = current_app.config.get("DATA_MANIFEST_PATH")

    return jsonify(
        {
            "mode": current_app.config.get("DATA_MODE"),
            "version": current_app.config.get("DATA_VERSION"),
            "manifestPath": manifest_path,
            "database": {"path": db_path, "exists": bool(db_path and os.path.exists(db_path))},
            "geojson": {
                "dir": geojson_dir,
                "exists": bool(geojson_dir and os.path.isdir(geojson_dir)),
            },
        }
    )
