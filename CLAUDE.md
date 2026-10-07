# Regulated Plants — Web App

Flask app that presents a global dataset of regulated invasive plant species. Deployed on Railway.

## Two repos, two deployments

| | `regulated_plants_app` (this repo) | `regulated_plants_data` (`../regulated-plants-data`) |
|---|---|---|
| Role | Public web app + landing pages + Swagger UI | Private data service: release artifacts + `/v1` REST API |
| Visibility | Public | Private |
| Deploy | Railway (gunicorn, `Procfile`) | Railway (separate service) |
| Owns | Presentation, accounts, auth, blog | The dataset, the ingestion pipeline, API keys |

They are coupled only by an HTTP pull. **The web app never writes to the data service.**

### Data flow

```
scientist CSVs                     (data repo: preprocessing_utils/data/current/)
  -> scripts/assign_species_ids.py  numbers new species, links new regulation rows
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

- **`species_id`** (e.g. `RP000487`) — `TEXT NOT NULL UNIQUE`, **ours**. One per regulated plant,
  **never changed** (not on rename, not when its GBIF taxon changes) and **never reused**. It is the
  join/lookup key for everything: regulations, the web app's APIs, the `/v1` API. Issued only by
  the data repo's `scripts/assign_species_ids.py`; every ID ever issued is in
  `preprocessing_utils/data/species_ids.csv` (with the pre-2026-10-07 `sp_<name>_<hash>` ID as
  `legacy_species_id`). Those legacy IDs embedded names, which went stale on rename; that is why
  they were replaced.
- **`gbif_taxon_id`** (e.g. `6P8ZF`) — `TEXT`, nullable, **not unique**: GBIF's **Catalogue of Life
  (COL XR)** taxon ID. Reference data, not identity. Hybrids may share a parent's ID and species
  with no exact match share their genus's (`plants.gbif_taxon_match`: `exact`, `variant`,
  `parent_fallback`, `genus_fallback`). GBIF only understands it with
  `checklistKey=GBIF_TAXON_CHECKLIST_KEY` (`7ddf754f-…`): `taxonKey=6P8ZF` alone returns
  **0 results, not an error**. Used for the photo gallery (`/species/api/photos/by-species-id/<id>`)
  and gbif.org links; `sameAs` uses it only for `exact`/`variant` matches.

GBIF's old numeric backbone key (`gbif_usage_key`) was removed from the sheets, database, API and
app on 2026-10-07: GBIF is retiring it. Nothing should reintroduce it.

**Page URLs are names, not IDs.** `/species/<species_slug(canonical_name)>` is what partners (CABI)
link to. Renaming a species changes its slug, so the data build records the old slug in
`plant_slug_aliases` (it compares names with the previous release, matched by `species_id`) and
`species.detail` 301-redirects old slugs. This only works because `species_id` survives renames.

### The researcher's sheets (from the researcher, 2026-10-07)

- **Matching rule:** hybrids may resolve to the parent taxon (species, subspecies or variety level);
  every other taxon with no exact GBIF match resolves to the **genus**, never to another species.
- **Species sheet:** `species_id` first, then `gbif_taxon_id` / `gbif_taxon_name` /
  `gbif_taxon_match`. New species arrive with a **blank** ID; we assign it.
- **Regulations sheet:** `species_id` (blank on new rows; we fill it), `listed_name` (the name
  **exactly as the source document writes it**: the evidence), `gbif_taxon_id` (the taxon the
  researcher **determined** that listing means). `assign_species_ids.py` links a row only if exactly
  one species has that taxon ID (or its accepted taxon) **and** `listed_name` is that species' name
  or a synonym; anything else goes to a review CSV. Rows with an ID are never re-linked.
- In v1.4 they set renamed species' IDs to `NA` (a rename looked like a new record to them). It is
  the same plant: same traits, same regulations. Rule given back: **same plant, keep the ID.**
- They share each species' ID, taxon ID and canonical name with CABI.
- Their v1.4 files came from Excel saved as Mac Roman, not UTF-8 (30 stray `0xCA` non-breaking
  spaces); ask for "CSV UTF-8".

### Synonyms

A synonym taxon ID still resolves, but **occurrences accumulate under the accepted taxon**, so
querying the synonym silently returns a fraction of the data (`Cardaria draba` `R4V2`: 1,664
occurrences with photos; the accepted `Lepidium draba` `6P8ZF`: 31,370).
`gbif_media._resolve_accepted_taxon_id()` follows synonyms at query time via the v2 match API's
`usageKey`, so the gallery is correct without touching the database. Anything else that queries
GBIF by taxon ID should do the same.

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
> `LOCAL_SAMPLE_DB_PATH=../regulated-plants-data/data/artifacts/weeds.db` (in `local_sample` mode
> `DATA_MODE` overwrites `DATABASE_PATH` with this, so setting `DATABASE_PATH` has no effect).
> `state_database.py` guards for schema drift with `_supports_plant_column`;
> `species_database.py` does not.

## Deployment (Railway)

`Procfile`: `web: gunicorn "app:create_app()"`. Note `create_app()` calls
`data_manager.ensure_ready()`, which **blocks on cold boot** while it downloads the artifact.

Key env vars (full table in `Readme.md`): `DATA_MODE=remote_production`,
`DATA_REMOTE_BASE_URL`, `DATA_REMOTE_TOKEN`, `APP_DATABASE_URL` (Postgres for accounts),
`AUTH_ADMIN_EMAILS`, `SECRET_KEY`, `POSTMARK_SERVER_TOKEN`, `RECAPTCHA_*`.

## Auth posture

**Source URLs are not published on the website** (decision of 2026-10-07: we don't want
people scraping the data). Show the authority name and year, never a link to the source
document. They may be used server-side (e.g. the method page groups jurisdictions that
share a source by URL). The API demo proxy (`demo_regulatory_check`) strips every
`source_url` from the upstream response before it reaches the browser.

Regulation *detail* is gated behind an approved researcher account
(`_species_regulation_payload` in `views.py` returns only a jurisdiction count to anonymous
users). Species names, traits, and GBIF photos are public.
