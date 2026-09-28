# Regulated Plants Database (Web App)

**An environmental compliance analytics platform**

> Business & policy analytics system for exploring regulated invasive plant species across jurisdictions. This repository contains the analytics delivery layer (web application + REST endpoints). The full global dataset and ingestion pipeline are maintained separately to ensure proper data governance; a California-only sample dataset is included here to enable reproducible local analysis and development.

![Website screenshot](./app/static/img/homepage_screenshot.png)

## Analytics context

Environmental compliance depends on knowing which plant species are regulated, where, and to what extent.
In practice, this information is fragmented across government sources, published in inconsistent formats, and difficult to compare across regions.

This project transforms raw regulatory lists into decision-ready intelligence by:
- Normalising jurisdictional and taxonomic data
- Designing interpretable regulatory intensity metrics
- Delivering geospatial and species-centric analytical views
- Supporting downstream use cases such as compliance screening and policy benchmarking

---

## Table of Contents
1. [Analytical Features](#analytical-features)
2. [Tech Stack](#tech-stack)
3. [Getting Started](#getting-started)
4. [Environment Configuration](#environment-configuration)
5. [Local Sample Data](#local-sample-data)
6. [Remote Data Service](#remote-data-service)
7. [Deployment](#deployment)
8. [Project Structure](#project-structure)
9. [Contributing](#contributing)

---

## Analytical Features
- **Geospatial regulatory analysis:** Interactive Leaflet map with fixed analytical colour thresholds representing regulatory intensity by jurisdiction.
- **Species-based analytical lookup:** Search regulated species to identify all jurisdictions where regulation applies, enabling cross-border risk assessment.
- **Layered regulatory scope**: Toggle regional, national, and international regulation layers to isolate policy drivers.
- **Tabular analytics & exports:** Structured tables support filtering, comparison, and downstream analysis.
- **Supporting methodology & sources:** Blog and methodology pages document analytical assumptions, data sources, and limitations.

## Tech Stack
- **Backend:** Flask, Postgres for account access, SQLite release artifacts for plant data
- **Frontend:** Bootstrap 5, Leaflet, DataTables, Select2, vanilla JS
- **Email & Security:** Flask-Mail, Flask-Limiter, reCAPTCHA

## Getting Started
This repository can be run locally using a self-contained analytical sample (California only).
```bash
# Clone the repo
git clone https://github.com/<your-org>/regulated_plants_app.git
cd regulated_plants_app

# Create & activate virtual environment
python3 -m venv weeds_env
source weeds_env/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Environment Configuration
Copy `.env.example` to `.env` (or export variables another way) and set:

| Variable | Description |
| --- | --- |
| `SECRET_KEY` | Flask session key |
| `PERMANENT_SESSION_LIFETIME_DAYS` | Researcher login session lifetime in days (default `90`) |
| `MAIL_DEFAULT_SENDER` | Verified Postmark sender address |
| `CONTACT_EMAIL` | Optional contact form recipient override (defaults to `MAIL_DEFAULT_SENDER`) |
| `EMAIL_SEND_TIMEOUT_SECONDS` | Timeout for email delivery (default `8`) |
| `POSTMARK_SERVER_TOKEN` | Postmark server token |
| `POSTMARK_MESSAGE_STREAM` | Postmark message stream (default `outbound`) |
| `RECAPTCHA_SITE_KEY` / `RECAPTCHA_SECRET_KEY` | Google reCAPTCHA keys |
| `DATA_MODE` | `local_sample` (default) or `remote_production` |
| `DATA_REMOTE_BASE_URL` | Base URL of the private data service (remote mode) |
| `DATA_REMOTE_TOKEN` | Bearer token for the data service (remote mode) |
| `DATA_MANIFEST_TTL_SECONDS` | Poll interval for data updates (default `0`, disabled) |
| `DATA_REMOTE_TIMEOUT_SECONDS` | Remote fetch timeout in seconds (default `90`) |
| `OOZR_BASE_URL` | OOZR dashboard base URL (example: `https://oozr.up.railway.app`) |
| `OOZR_PROJECT_SLUG` | Project slug for activations (default `regulatedplants`) |
| `OOZR_METRICS_ENABLED` | Enable activation tracking (`1`/`0`, default `0`) |
| `APP_DATABASE_URL` | Postgres connection URL for web app accounts, login tokens, and admin audit events |
| `AUTH_ADMIN_EMAILS` | Comma-separated admin emails. These accounts are bootstrapped as approved admins when `APP_DATABASE_URL` is configured |
| `AUTH_DEV_SHOW_MAGIC_LINK` | Show login link on the confirmation page for development (`1`/`0`, default `0`) |
| `AUTH_ROR_ENABLED` | Enable ROR-backed affiliation autocomplete and ROR domain matching (`1`/`0`, default `1`) |
| `AUTH_ROR_ALLOWED_TYPES` | Comma-separated ROR organization types eligible for domain matching (default `education,government,facility,healthcare,nonprofit`) |
| `ROR_API_BASE_URL` | ROR organizations API base URL (default `https://api.ror.org/v2/organizations`) |
| `ROR_API_TIMEOUT_SECONDS` | Timeout for ROR API calls (default `4`) |
| `GBIF_PHOTOS_ENABLED` | Show the GBIF photo gallery on the species page (`1`/`0`, default `1`) |
| `GBIF_API_BASE_URL` | GBIF API base URL (default `https://api.gbif.org/v1`) |
| `GBIF_API_TIMEOUT_SECONDS` | Timeout for GBIF API calls (default `8`) |
| `GBIF_CONTACT_EMAIL` | Address GBIF can use to reach the maintainers (default `lindley@menacon.com`) |
| `GBIF_API_USER_AGENT` | Full override of the contact string sent to GBIF. GBIF asks integrators to include a URL or email so they can get in touch about problem traffic. Defaults to `regulated-plants-app/1.0 (+BASE_URL; mailto:GBIF_CONTACT_EMAIL)` |
| `GBIF_PHOTO_LIMIT` | Photos per species (default `5`, which fills the gallery layout exactly) |
| `GBIF_PHOTO_CACHE_TTL_SECONDS` | In-process cache lifetime for photo lookups (default `86400`) |

The app reads these via `Config` in `app/config.py`.

## Account Access
The web app uses a Postgres-backed account lifecycle:

- `/auth/signup` creates or updates a pending account request with name, email, organization, and reason for access.
- `/auth/login` sends a one-time email login link only for approved accounts.
- `/admin/accounts` lets configured admins approve, reject, and revoke accounts.

The account schema is created by application code on startup when `APP_DATABASE_URL` is configured. Do not create the tables manually. For Railway, provision a Postgres service and set `APP_DATABASE_URL` on the web service to that database connection URL. Keep `AUTH_ADMIN_EMAILS` configured so at least one admin can sign in and review requests.

## OOZR Activation Tracking
This research project tracks one signal only: activation.

- **Aha moment**: first time a unique user clicks the map and receives regulated species results.
- Anonymous user identity is stored in browser cookie `anonymous_user_id`.
- After successful activation send, cookie `aha_activated=1` is set to prevent repeat emits.
- Activation is sent to OOZR canonical endpoint:
  - `POST {OOZR_BASE_URL}/api/activate`
  - payload: `{ "project": "regulatedplants", "anonymous_id": "...", "timestamp": "ISO-8601" }`

## Local Sample Data
This repo includes a minimal California-only sample dataset for local use:

- `app/static/data/sample/weeds_sample.db`
- `app/static/data/sample/geojson/united_states.geojson`

`DATA_MODE=local_sample` uses these by default.

## Remote Data Service and Governance
In production, the application consumes versioned analytical artifacts from a private data service.

This separation reflects real-world analytics practice:
- Controlled data stewardship
- Licensing and source attribution
- Safe public consumption of derived insights

Expected endpoints on the data service:
- `GET /manifest.json`
- `GET /artifacts/weeds.db`
- `GET /artifacts/geojson/<file>.geojson`

The manifest may include a non-detailed release history for the website footer
and Methodology page:

```json
{
  "version": "20260528T124621Z",
  "generated_at": "2026-05-28T12:46:21Z",
  "metrics": {
    "taxa": 2047,
    "jurisdictions": 103,
    "regulation_rows": 5523
  },
  "release_history": [
    {
      "version": "20260528T124621Z",
      "generated_at": "2026-05-28T12:46:21Z",
      "summary": "Current public data release",
      "metrics": {
        "taxa": 2047,
        "jurisdictions": 103,
        "regulation_rows": 5523
      }
    }
  ]
}
```

If `release_history` is absent, the app shows the current release as the only
history entry.

Remote data behavior in `remote_production`:
- If a valid local cache exists, boot immediately from cache.
- Refresh runs in the background only when `DATA_MANIFEST_TTL_SECONDS > 0`.
- If refresh fails (timeout/checksum/network), the app keeps serving the last valid cache.
- Only first-ever cold start (no cache) blocks on remote bootstrap.

The data service lives in a separate private repo (e.g., `regulated_plants_data`).

## Website API Scope
This repository exposes the website-facing API only (global and optimized for the site UX).

Current routes include:
- `/api/region-weed-counts`
- `/api/region`
- `/api/geojson-files`
- `/api/home-highlights`
- `/species/api/search`
- `/species/api/weed-states/by-key/<usage_key>`

A separate stricter external compliance API (US-focused, versioned, partner-facing) is planned as a distinct surface.

## Deployment
1. Set environment variables for production.
2. Use `gunicorn main:app` or `Procfile` for your platform.
3. Ensure the data service URL + token are configured.
The live deployment is hosted under an institutional domain and used by public and academic stakeholders.

## Project Structure
```
regulated_plants_app/
├── app/
│   ├── static/         # JS, CSS, images, sample data
│   ├── templates/      # Jinja templates
│   ├── utils/          # Database + helper classes
│   └── views.py        # Flask blueprints & routes
├── requirements.txt
├── Procfile
└── main.py             # Flask entrypoint
```

## Contributing
Contributions are welcome, particularly in areas related to:
- Analytical extensions
- Data validation or quality checks
- New jurisdiction support (with documented sources)

1. Fork + branch from main
2. Keep PRs focused and documented
3. Update docs or methodology notes where relevant
