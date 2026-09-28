# Regulated Plants — Web App

Flask app that presents a global dataset of regulated invasive plant species. Deployed on Railway.

## Two repos, two deployments

| | `regulated_plants_app` (this repo) | `regulated_plants_data` (`../regulated_plants_data`) |
|---|---|---|
| Role | Public web app + landing pages + Swagger UI | Private data service: release artifacts + `/v1` REST API |
| Visibility | Public | Private |
| Deploy | Railway (gunicorn, `Procfile`) | Railway (separate service) |
| Owns | Presentation, accounts, auth, blog | The dataset, the ingestion pipeline, API keys |

They are coupled only by an HTTP pull. **The web app never writes to the data service.**

### Data flow

```
scientist CSVs                     (data repo: preprocessing_utils/data/current/)
  -> create_database.py            builds data/artifacts/weeds.db + validation_report.json
  -> scripts/generate_manifest.py  cuts an immutable release, flips data/manifest.json
  -> Railway (data service)        serves /manifest.json + /releases/<ver>/artifacts/...  (bearer auth)
  -> DataManager (this repo)       polls manifest, sha256-verifies, downloads weeds.db into data_cache/
  -> SpeciesDatabase / StateDatabase   read that SQLite file
  -> Flask JSON endpoints -> browser JS
```

Data updates ship **without redeploying the web app** — `DataManager.maybe_refresh()` runs in a
`before_request` hook and swaps the DB file in place, evicting the cached DB handles from
`app.extensions`.

## Layout

```
main.py                     dev entrypoint (gunicorn uses "app:create_app()")
app/__init__.py             app factory: extensions, DataManager boot, blueprints, security headers
app/config.py               single flat Config class, every setting via os.getenv
app/views.py                all public blueprints: home, species, blog, method, api_page, about
app/auth_routes.py          magic-link signup/login (Postgres-backed)
app/admin_routes.py         /admin/accounts approval queue
app/utils/
  data_manager.py           manifest polling, sha256 download, atomic swap, TTL refresh
  database_base.py          sqlite3 connection helper (row_factory = sqlite3.Row)
  species_database.py       species search + per-species regulation lookups
  state_database.py         map / jurisdiction queries
  gbif_media.py             GBIF occurrence photos for the species page
  ror_client.py             ROR affiliation lookup (the reference external-API client)
  account_store.py          Postgres account lifecycle
app/templates/              Jinja, base.html is the layout
app/static/{css,js,img}/    one CSS file per page, one JS file per page
```

## Conventions worth matching

- **Config**: `app/config.py` uses **3-space indent** (not 4 — match it). Bools are
  `os.getenv('X','0').strip().lower() in {'1','true','yes','on'}`; ints are `int(os.getenv('X','8'))`.
- **External API clients** live in `app/utils/`, are **Flask-agnostic** (base URL and timeout are
  passed as arguments, never read from `current_app`), use **stdlib `urllib`**, and expose a
  narrow normalising function that returns a small stable dict. `ror_client.py` and
  `gbif_media.py` are the two examples.
- **Singletons** live in `app.extensions[...]`, created lazily (see `_get_species_db` in `views.py`).
  There is no Flask-Caching / Redis — in-process dicts with a TTL are the house pattern.
- **Frontend is Bootstrap 5.1.3 + jQuery + select2 from CDN.** No build step, no bundler, no
  framework. Page JS is a single `DOMContentLoaded` closure.
- **Design system** is in `app/static/css/style.css` `:root`: `--unu-blue: #15234A`,
  `--ucd-gold: #fcbc04`, plus greys. House style is flat — hairline `#e9ecef` borders,
  `0.5rem` radius, **no box shadows**.
- Rate-limited routes use `@limiter.limit(...)`, which **replaces** the global
  `["200 per day", "50 per hour"]` default for that endpoint.

## Species identity — the one thing to get right

Two identifiers, and they are not interchangeable:

- **`species_id`** (e.g. `sp_acacia_dealbata_fa2899c4`) — `TEXT NOT NULL UNIQUE`. This is the
  **stable join/lookup key**. Use it for anything that resolves to one row.
- **`gbif_usage_key`** — `INTEGER NOT NULL`, **not unique**. It is a GBIF *backbone taxon key*
  (the `usageKey` from GBIF's species-match API), used for links to gbif.org and for GBIF
  occurrence/media queries. 12 rows share a key with a parent taxon (hybrids collapse onto the
  parent), and ~97 keys are genus-rank rather than species-rank.

It is **not** a GBIF occurrence key. Occurrence keys are ~10 digits; taxon keys here are 7-8.
This matters for the media API — see `app/utils/gbif_media.py`.

### Backbone drift — audit of 2026-08-02

All 2,192 stored keys were checked against `api.gbif.org/v1/species/<key>`:

| | |
|---|---|
| Keys that no longer resolve (404) | **0** |
| Keys GBIF has remapped (`nubKey` != ours) | **0** |
| Keys now flagged `SYNONYM` | **30** |
| Keys with `DOUBTFUL` status | 6 |
| Canonical-name drift vs our stored name | 67 (26 cosmetic `subsp.`/`var.` formatting, 41 genuine) |

So nothing is deprecated and nothing is about to break. The real issue is the 30 synonyms:
the old key still resolves, but **occurrences accumulate under the accepted key**, so querying
the synonym silently returns a fraction of the data. `Cardaria draba` (3052311) has 22
occurrences with photos; the accepted `Lepidium draba` (5376961) has 22,689.

`gbif_media._resolve_accepted_key()` follows synonyms at query time, so the gallery is correct
without touching the database. Anything else that queries GBIF by taxon key should do the same.
Re-run the audit after each GBIF backbone release:
`scripts/audit_gbif_keys.py` in the data repo is the place for it if it gets promoted from scratch.

## Local development

```bash
source weeds_env/bin/activate
pip install -r requirements.txt
python main.py            # http://localhost:3000
```

`DATA_MODE=local_sample` (the default) reads `app/static/data/sample/weeds_sample.db`.

> **Known gotcha:** that sample DB is on a **stale schema** — it has no `plants.species_id`
> column, so `SpeciesDatabase.search_weeds()` (which selects `p.species_id`) raises
> `OperationalError` against it. The species page therefore does not work in `local_sample`
> mode. To work on the species page, point at a real artifact:
> `DATABASE_PATH=../regulated_plants_data/data/artifacts/weeds.db`.
> `state_database.py` guards for schema drift with `_supports_plant_column`;
> `species_database.py` does not.

## Deployment (Railway)

`Procfile`: `web: gunicorn "app:create_app()"`. Note `create_app()` calls
`data_manager.ensure_ready()`, which **blocks on cold boot** while it downloads the artifact.

Key env vars (full table in `Readme.md`): `DATA_MODE=remote_production`,
`DATA_REMOTE_BASE_URL`, `DATA_REMOTE_TOKEN`, `APP_DATABASE_URL` (Postgres for accounts),
`AUTH_ADMIN_EMAILS`, `SECRET_KEY`, `POSTMARK_SERVER_TOKEN`, `RECAPTCHA_*`.

## Auth posture

Regulation *detail* is gated behind an approved researcher account
(`_species_regulation_payload` in `views.py` returns only a jurisdiction count to anonymous
users). Species names, traits, and GBIF photos are public.
