import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from app.utils.database_base import DatabaseBase

EU_MEMBERS = {
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia",
    "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
    "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
    "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia",
    "Slovenia", "Spain", "Sweden"
}


class StateDatabase(DatabaseBase):
    """Region-level map + table queries using normalized schema."""

    def __init__(self, db_path: str = "weeds.db", geojson_dir: str = None):
        super().__init__(db_path=db_path, geojson_dir=geojson_dir)
        self._geo_regions_cache: Optional[List[Dict]] = None
        self._geo_regions_signature: Optional[Tuple] = None
        self._jurisdiction_columns_cache: Optional[set] = None
        self._plant_columns_cache: Optional[set] = None

    COUNTRY_NAME_ALIASES = {
        "federal republic of germany": "Germany",
        "the federal republic of germany": "Germany",
        "deutschland": "Germany",
        "kingdom of saudi arabia": "Saudi Arabia",
        "united states of america": "United States",
    }

    REGION_NAME_CANDIDATES = (
        "region",
        "REGION",
        "STATE_NAME",
        "state",
        "STATE",
        "name",
        "NAME",
        "shapeName",
    )

    @staticmethod
    def _primary_common_name(value: str, fallback: str = None) -> str:
        raw = (value or "").strip()
        if not raw:
            return fallback
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        return parts[0] if parts else (fallback or raw)

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(str(value or "").strip().split())

    def _canonical_country_name(self, value: str) -> str:
        normalized = self._normalize_text(value)
        if not normalized:
            return ""
        return self.COUNTRY_NAME_ALIASES.get(normalized.lower(), normalized)

    def _canonical_region_name(self, value: str) -> str:
        return self._normalize_text(value)

    @staticmethod
    def _slugify(value: str) -> str:
        text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
        return text.strip("-")

    def _region_key(self, country: str, region: str) -> Tuple[str, str]:
        return (
            self._canonical_country_name(country),
            self._canonical_region_name(region),
        )

    def _infer_country_from_filename(self, filename: str) -> str:
        base = filename[:-8] if filename.lower().endswith(".geojson") else filename
        base = base.replace("_", " ").replace("-", " ").strip()
        pretty = " ".join(w.capitalize() for w in base.split())
        return self._canonical_country_name(pretty)

    def _extract_region_name_from_props(self, props: Dict, country: str) -> str:
        saw_country_level = False
        for key in self.REGION_NAME_CANDIDATES:
            raw = props.get(key)
            if not raw:
                continue
            value = self._canonical_region_name(raw)
            if not value:
                continue
            if country:
                canonical = self._canonical_country_name(value)
                if canonical and canonical.lower() == country.lower():
                    saw_country_level = True
                    continue
            if saw_country_level:
                continue
            return value
        if saw_country_level and country:
            return country
        return country

    def _geo_regions_signature_for_dir(self, geojson_dir: str) -> Optional[Tuple]:
        if not geojson_dir or not os.path.isdir(geojson_dir):
            return None
        parts = []
        for name in sorted(os.listdir(geojson_dir)):
            if not name.lower().endswith(".geojson"):
                continue
            full_path = os.path.join(geojson_dir, name)
            try:
                parts.append((name, int(os.path.getmtime(full_path))))
            except OSError:
                parts.append((name, 0))
        return tuple(parts)

    def _geo_regions_signature_for_db(self) -> Optional[Tuple]:
        if not self.db_path or not os.path.exists(self.db_path):
            return None
        try:
            return ("db", int(os.path.getmtime(self.db_path)))
        except OSError:
            return ("db", 0)

    def _table_exists(self, conn, table_name: str) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            (table_name,),
        ).fetchone()
        return bool(row)

    def _load_geo_regions_from_db(self) -> List[Dict]:
        conn = self.get_connection()
        try:
            if not self._table_exists(conn, "geo_regions"):
                return []
            rows = conn.execute(
                """
                SELECT
                    geo_region_id,
                    geojson_slug,
                    country,
                    region,
                    COALESCE(NULLIF(TRIM(jurisdiction_uid), ''), '') AS jurisdiction_uid
                FROM geo_regions
                ORDER BY geojson_slug ASC, region ASC
                """
            ).fetchall()
            if not rows:
                return []

            regions: List[Dict] = []
            for row in rows:
                country = self._canonical_country_name(row["country"])
                region = self._canonical_region_name(row["region"])
                if not country or not region:
                    continue
                regions.append(
                    {
                        "geo_region_id": row["geo_region_id"],
                        "geojson_slug": row["geojson_slug"],
                        "country": country,
                        "region": region,
                        "display_name": region if region != country else country,
                        "jurisdiction_uid": row["jurisdiction_uid"] or None,
                    }
                )
            return regions
        finally:
            conn.close()

    def _load_geo_regions(self) -> List[Dict]:
        db_signature = self._geo_regions_signature_for_db()
        if db_signature == self._geo_regions_signature and self._geo_regions_cache is not None:
            return self._geo_regions_cache

        db_regions = self._load_geo_regions_from_db()
        if db_regions:
            self._geo_regions_cache = db_regions
            self._geo_regions_signature = db_signature
            return db_regions

        geojson_dir = self.geojson_dir or ""
        signature = self._geo_regions_signature_for_dir(geojson_dir)
        if signature == self._geo_regions_signature and self._geo_regions_cache is not None:
            return self._geo_regions_cache

        regions: List[Dict] = []
        seen_ids = set()
        if not geojson_dir or not os.path.isdir(geojson_dir):
            self._geo_regions_cache = []
            self._geo_regions_signature = signature
            return []

        for filename in sorted(os.listdir(geojson_dir)):
            if not filename.lower().endswith(".geojson"):
                continue
            geojson_slug = filename[:-8].lower()
            country = self._infer_country_from_filename(filename)
            file_path = os.path.join(geojson_dir, filename)

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                continue

            for feature in payload.get("features", []):
                props = feature.get("properties") or {}
                region = self._extract_region_name_from_props(props, country)
                if not country or not region:
                    continue
                geo_region_id = f"geo:{geojson_slug}:{self._slugify(region)}"
                if geo_region_id in seen_ids:
                    continue
                seen_ids.add(geo_region_id)
                regions.append(
                    {
                        "geo_region_id": geo_region_id,
                        "geojson_slug": geojson_slug,
                        "country": country,
                        "region": region,
                        "display_name": region if region != country else country,
                        "jurisdiction_uid": self._fallback_jurisdiction_uid(country, region, "region"),
                    }
                )

        self._geo_regions_cache = regions
        self._geo_regions_signature = signature
        return regions

    def _geo_region_index(self) -> Dict[str, Dict]:
        return {row["geo_region_id"]: row for row in self._load_geo_regions()}

    def _jurisdiction_columns(self, conn) -> set:
        if self._jurisdiction_columns_cache is not None:
            return self._jurisdiction_columns_cache
        rows = conn.execute("PRAGMA table_info(jurisdictions)").fetchall()
        self._jurisdiction_columns_cache = {row["name"] for row in rows}
        return self._jurisdiction_columns_cache

    def _supports_jurisdiction_column(self, conn, name: str) -> bool:
        return name in self._jurisdiction_columns(conn)

    def _plant_columns(self, conn) -> set:
        if self._plant_columns_cache is not None:
            return self._plant_columns_cache
        rows = conn.execute("PRAGMA table_info(plants)").fetchall()
        self._plant_columns_cache = {row["name"] for row in rows}
        return self._plant_columns_cache

    def _supports_plant_column(self, conn, name: str) -> bool:
        return name in self._plant_columns(conn)

    def _fallback_jurisdiction_uid(self, country: str, region: str, j_type: str) -> str:
        country_part = self._slugify(country)
        region_part = self._slugify(region) if region else "country"
        return f"{j_type}:{country_part}:{region_part}"

    def get_highlight_metrics(self, include_counts: bool = True) -> Dict:
        conn = self.get_connection()
        try:
            species_count = None
            regulation_count = None
            jurisdiction_count = None

            if include_counts:
                species_count = conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM plants
                    """
                ).fetchone()["count"] or 0

                regulation_count = conn.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM regulations
                    WHERE is_webapp_scoped = 1
                    """
                ).fetchone()["count"] or 0

                region_j = conn.execute(
                    """
                    SELECT COUNT(DISTINCT j.country || '::' || j.region) AS count
                    FROM jurisdictions j
                    WHERE j.jurisdiction_type = 'region'
                      AND j.country IS NOT NULL AND TRIM(j.country) != ''
                      AND j.region IS NOT NULL AND TRIM(j.region) != ''
                      AND EXISTS (
                          SELECT 1
                          FROM regulations r
                          WHERE r.jurisdiction_id = j.id
                            AND r.is_webapp_scoped = 1
                      )
                    """
                ).fetchone()["count"] or 0

                national_j = conn.execute(
                    """
                    SELECT COUNT(DISTINCT j.country) AS count
                    FROM jurisdictions j
                    WHERE j.jurisdiction_type = 'national'
                      AND j.country IS NOT NULL AND TRIM(j.country) != ''
                      AND EXISTS (
                          SELECT 1
                          FROM regulations r
                          WHERE r.jurisdiction_id = j.id
                            AND r.is_webapp_scoped = 1
                      )
                    """
                ).fetchone()["count"] or 0

                international_j = conn.execute(
                    """
                    SELECT COUNT(
                        DISTINCT COALESCE(NULLIF(TRIM(j.jurisdiction_group), ''), NULLIF(TRIM(j.country), ''), 'International')
                    ) AS count
                    FROM jurisdictions j
                    WHERE j.jurisdiction_type = 'international'
                      AND EXISTS (
                          SELECT 1
                          FROM regulations r
                          WHERE r.jurisdiction_id = j.id
                            AND r.is_webapp_scoped = 1
                      )
                    """
                ).fetchone()["count"] or 0

                jurisdiction_count = region_j + national_j + international_j

            latest_country_row = conn.execute(
                """
                SELECT j.country
                FROM jurisdictions j
                WHERE j.country IS NOT NULL AND TRIM(j.country) != ''
                  AND EXISTS (
                      SELECT 1
                      FROM regulations r
                      WHERE r.jurisdiction_id = j.id
                        AND r.is_webapp_scoped = 1
                  )
                ORDER BY j.id DESC
                LIMIT 1
                """
            ).fetchone()
            latest_country = latest_country_row["country"] if latest_country_row else None

            latest_country_regions = 0
            latest_country_region = None
            if latest_country:
                latest_country_regions = conn.execute(
                    """
                    SELECT COUNT(DISTINCT j.region) AS count
                    FROM jurisdictions j
                    WHERE j.jurisdiction_type = 'region'
                      AND j.country = ?
                      AND j.region IS NOT NULL AND TRIM(j.region) != ''
                      AND EXISTS (
                          SELECT 1
                          FROM regulations r
                          WHERE r.jurisdiction_id = j.id
                            AND r.is_webapp_scoped = 1
                      )
                    """,
                    (latest_country,),
                ).fetchone()["count"] or 0

                row = conn.execute(
                    """
                    SELECT j.region
                    FROM jurisdictions j
                    WHERE j.jurisdiction_type = 'region'
                      AND j.country = ?
                      AND j.region IS NOT NULL AND TRIM(j.region) != ''
                      AND EXISTS (
                          SELECT 1
                          FROM regulations r
                          WHERE r.jurisdiction_id = j.id
                            AND r.is_webapp_scoped = 1
                      )
                    ORDER BY j.region ASC
                    LIMIT 1
                    """,
                    (latest_country,),
                ).fetchone()
                latest_country_region = row["region"] if row else None

            top_species_row = conn.execute(
                """
                SELECT
                    p.canonical_name,
                    COUNT(DISTINCT j.country || '::' || j.region) AS jurisdiction_count
                FROM regulations r
                JOIN plants p ON p.id = r.plant_id
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                  AND j.jurisdiction_type = 'region'
                  AND j.country IS NOT NULL AND TRIM(j.country) != ''
                  AND j.region IS NOT NULL AND TRIM(j.region) != ''
                GROUP BY p.canonical_name
                ORDER BY jurisdiction_count DESC, p.canonical_name ASC
                LIMIT 1
                """
            ).fetchone()

            top_species = None
            if top_species_row:
                common_name_row = conn.execute(
                    """
                    SELECT english_name
                    FROM plants
                    WHERE canonical_name = ?
                      AND english_name IS NOT NULL
                      AND TRIM(english_name) != ''
                    LIMIT 1
                    """,
                    (top_species_row["canonical_name"],),
                ).fetchone()
                common_name = None
                if common_name_row and common_name_row["english_name"]:
                    common_name = common_name_row["english_name"].split(",")[0].strip()

                top_species = {
                    "name": top_species_row["canonical_name"],
                    "common_name": common_name,
                    "jurisdiction_count": top_species_row["jurisdiction_count"],
                }

            top_j_row = conn.execute(
                """
                SELECT
                    j.country,
                    j.region,
                    COUNT(DISTINCT p.id) AS species_count
                FROM regulations r
                JOIN plants p ON p.id = r.plant_id
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                  AND j.jurisdiction_type = 'region'
                  AND j.country IS NOT NULL AND TRIM(j.country) != ''
                  AND j.region IS NOT NULL AND TRIM(j.region) != ''
                GROUP BY j.country, j.region
                ORDER BY species_count DESC, j.region ASC
                LIMIT 1
                """
            ).fetchone()

            top_jurisdiction = None
            if top_j_row:
                top_jurisdiction = {
                    "name": top_j_row["region"],
                    "country": top_j_row["country"],
                    "species_count": top_j_row["species_count"],
                }

            return {
                "species_count": species_count,
                "regulation_count": regulation_count,
                "jurisdiction_count": jurisdiction_count,
                "latest_country": latest_country,
                "latest_country_regions": latest_country_regions,
                "latest_country_region": latest_country_region,
                "top_species": top_species,
                "top_jurisdiction": top_jurisdiction,
            }
        finally:
            conn.close()

    def get_weeds_for_geo_region(
        self,
        geo_region_id: str,
        include_region: bool = True,
        include_national: bool = True,
        include_international: bool = True,
    ) -> Dict:
        if not geo_region_id:
            return {"weeds": [], "has_any_data": False, "geo_region": None}

        geo_region = self._geo_region_index().get(geo_region_id)
        if not geo_region:
            return {"weeds": [], "has_any_data": False, "geo_region": None}

        country = geo_region["country"]
        region = geo_region["region"]
        jurisdiction_uid = geo_region.get("jurisdiction_uid")
        has_exact_region_mapping = bool(jurisdiction_uid)

        conn = self.get_connection()
        try:
            clauses = []
            params = []
            has_uid_column = self._supports_jurisdiction_column(conn, "jurisdiction_uid")
            species_id_expr = "p.species_id" if self._supports_plant_column(conn, "species_id") else "NULL"

            if include_region:
                if jurisdiction_uid and has_uid_column:
                    clauses.append(
                        f"""
                        SELECT
                            p.canonical_name,
                            p.english_name AS common_name,
                            p.family_name,
                            {species_id_expr} AS species_id,
                            p.gbif_usage_key AS usage_key,
                            COALESCE(NULLIF(TRIM(j.authority_name), ''), 'Unknown') AS source_authority,
                            'region' AS count_source_level
                        FROM regulations r
                        JOIN plants p ON p.id = r.plant_id
                        JOIN jurisdictions j ON j.id = r.jurisdiction_id
                        WHERE r.is_webapp_scoped = 1
                          AND j.jurisdiction_type = 'region'
                          AND LOWER(TRIM(j.jurisdiction_uid)) = LOWER(TRIM(?))
                        """
                    )
                    params.append(jurisdiction_uid)
                else:
                    clauses.append(
                        f"""
                        SELECT
                            p.canonical_name,
                            p.english_name AS common_name,
                            p.family_name,
                            {species_id_expr} AS species_id,
                            p.gbif_usage_key AS usage_key,
                            COALESCE(NULLIF(TRIM(j.authority_name), ''), 'Unknown') AS source_authority,
                            'region' AS count_source_level
                        FROM regulations r
                        JOIN plants p ON p.id = r.plant_id
                        JOIN jurisdictions j ON j.id = r.jurisdiction_id
                        WHERE r.is_webapp_scoped = 1
                          AND j.jurisdiction_type = 'region'
                          AND j.country = ?
                          AND j.region = ?
                        """
                    )
                    params.extend([country, region])

            if include_national:
                clauses.append(
                    f"""
                    SELECT
                        p.canonical_name,
                        p.english_name AS common_name,
                        p.family_name,
                        {species_id_expr} AS species_id,
                        p.gbif_usage_key AS usage_key,
                        COALESCE(NULLIF(TRIM(j.authority_name), ''), 'Unknown') AS source_authority,
                        'national' AS count_source_level
                    FROM regulations r
                    JOIN plants p ON p.id = r.plant_id
                    JOIN jurisdictions j ON j.id = r.jurisdiction_id
                    WHERE r.is_webapp_scoped = 1
                      AND j.jurisdiction_type = 'national'
                      AND j.country = ?
                      AND (j.region IS NULL OR TRIM(j.region) = '')
                    """
                )
                params.append(country)

            if include_international and country in EU_MEMBERS:
                clauses.append(
                    f"""
                    SELECT
                        p.canonical_name,
                        p.english_name AS common_name,
                        p.family_name,
                        {species_id_expr} AS species_id,
                        p.gbif_usage_key AS usage_key,
                        COALESCE(NULLIF(TRIM(j.authority_name), ''), 'Unknown') AS source_authority,
                        'international' AS count_source_level
                    FROM regulations r
                    JOIN plants p ON p.id = r.plant_id
                    JOIN jurisdictions j ON j.id = r.jurisdiction_id
                    WHERE r.is_webapp_scoped = 1
                      AND j.jurisdiction_type = 'international'
                      AND j.jurisdiction_group = 'EU'
                    """
                )

            if not clauses:
                return {"weeds": [], "has_any_data": self.country_has_data(country), "geo_region": geo_region}

            rows = conn.execute(f"{' UNION ALL '.join(clauses)}", params).fetchall()

            priority = {"region": 3, "national": 2, "international": 1}
            chosen = {}
            scopes = {}

            for row in rows:
                data = dict(row)
                canonical_name = data["canonical_name"]
                jurisdiction = data["count_source_level"]

                if canonical_name not in scopes:
                    scopes[canonical_name] = set()
                scopes[canonical_name].add(jurisdiction)

                existing = chosen.get(canonical_name)
                if not existing:
                    chosen[canonical_name] = data
                    continue

                existing_priority = priority.get(existing["count_source_level"], 0)
                new_priority = priority.get(jurisdiction, 0)
                if new_priority > existing_priority:
                    chosen[canonical_name] = data

            level_map = {"region": "Regional", "national": "National", "international": "International"}

            results = []
            for species in chosen.values():
                canonical_name = species["canonical_name"]
                species_scopes = scopes.get(canonical_name, set())
                results.append(
                    {
                        "canonical_name": canonical_name,
                        "common_name": self._primary_common_name(
                            species.get("common_name"),
                            canonical_name,
                        ),
                        "family_name": species.get("family_name"),
                        "species_id": species.get("species_id"),
                        "usage_key": species.get("usage_key"),
                        "level": level_map.get(species["count_source_level"], "Unknown"),
                        "count_source_level": species["count_source_level"],
                        "jurisdiction_match": "exact_mapped" if has_exact_region_mapping else "country_overlay",
                        "source_authority": species.get("source_authority"),
                        "has_national_regulation": "national" in species_scopes,
                        "has_international_regulation": "international" in species_scopes,
                    }
                )

            return {
                "weeds": sorted(results, key=lambda x: x["canonical_name"] or ""),
                "has_any_data": self.country_has_data(country),
                "geo_region": geo_region,
            }
        finally:
            conn.close()

    def get_weeds_for_region(
        self,
        country: str,
        region: str,
        include_region: bool = True,
        include_national: bool = True,
        include_international: bool = True,
    ) -> List[Dict]:
        country = self._canonical_country_name(country)
        region = self._canonical_region_name(region)
        for geo_region in self._load_geo_regions():
            if self._region_key(geo_region["country"], geo_region["region"]) == (country, region):
                payload = self.get_weeds_for_geo_region(
                    geo_region["geo_region_id"],
                    include_region=include_region,
                    include_national=include_national,
                    include_international=include_international,
                )
                return payload.get("weeds", [])
        return []

    def country_has_data(self, country: str) -> bool:
        if not country:
            return False

        conn = self.get_connection()
        try:
            if country in EU_MEMBERS:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM regulations r
                    JOIN jurisdictions j ON j.id = r.jurisdiction_id
                    WHERE r.is_webapp_scoped = 1
                      AND (
                          j.country = ?
                          OR (j.jurisdiction_type = 'international' AND j.jurisdiction_group = 'EU')
                      )
                    LIMIT 1
                    """,
                    (country,),
                ).fetchone()
                return bool(row)

            row = conn.execute(
                """
                SELECT 1
                FROM regulations r
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                  AND j.country = ?
                LIMIT 1
                """,
                (country,),
            ).fetchone()
            return bool(row)
        finally:
            conn.close()

    def get_region_weed_counts(
        self,
        include_region: bool = True,
        include_national: bool = True,
        include_international: bool = True,
    ) -> List[Dict]:
        geo_regions = self._load_geo_regions()
        if not geo_regions:
            return []

        conn = self.get_connection()
        try:
            if not include_region and not include_national and not include_international:
                return [
                    {
                        "geo_region_id": row["geo_region_id"],
                        "geojson_slug": row["geojson_slug"],
                        "country": row["country"],
                        "region": row["region"],
                        "count": 0,
                        "count_source_level": "none",
                        "jurisdiction_match": "none",
                        "regulation_status": "unknown",
                    }
                    for row in geo_regions
                ]

            national_rows = conn.execute(
                """
                SELECT j.country, r.plant_id
                FROM regulations r
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                  AND j.jurisdiction_type = 'national'
                  AND j.country IS NOT NULL AND TRIM(j.country) != ''
                  AND (j.region IS NULL OR TRIM(j.region) = '')
                """
            ).fetchall()

            eu_rows = conn.execute(
                """
                SELECT r.plant_id
                FROM regulations r
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                  AND j.jurisdiction_type = 'international'
                  AND j.jurisdiction_group = 'EU'
                """
            ).fetchall()

            region_sets = defaultdict(set)
            mapped_region_meta = {}

            has_geo_regions = self._table_exists(conn, "geo_regions")
            has_uid = self._supports_jurisdiction_column(conn, "jurisdiction_uid")
            has_status = self._supports_jurisdiction_column(conn, "regulation_status")

            if has_geo_regions and has_uid:
                region_rows = conn.execute(
                    """
                    SELECT gr.geo_region_id, r.plant_id
                    FROM geo_regions gr
                    JOIN jurisdictions j
                      ON LOWER(TRIM(j.jurisdiction_uid)) = LOWER(TRIM(gr.jurisdiction_uid))
                     AND j.jurisdiction_type = 'region'
                    JOIN regulations r
                      ON r.jurisdiction_id = j.id
                     AND r.is_webapp_scoped = 1
                    """
                ).fetchall()
                for row in region_rows:
                    region_sets[row["geo_region_id"]].add(row["plant_id"])

                status_expr = (
                    "COALESCE(NULLIF(TRIM(j.regulation_status), ''), 'no_regulation')"
                    if has_status
                    else "'no_regulation'"
                )
                mapped_rows = conn.execute(
                    f"""
                    SELECT
                        gr.geo_region_id,
                        COALESCE(NULLIF(TRIM(gr.jurisdiction_uid), ''), '') AS geo_jurisdiction_uid,
                        COALESCE(NULLIF(TRIM(j.jurisdiction_uid), ''), '') AS jurisdiction_uid,
                        CASE WHEN j.id IS NULL THEN 0 ELSE 1 END AS has_region_jurisdiction,
                        {status_expr} AS regulation_status
                    FROM geo_regions gr
                    LEFT JOIN jurisdictions j
                      ON LOWER(TRIM(j.jurisdiction_uid)) = LOWER(TRIM(gr.jurisdiction_uid))
                     AND j.jurisdiction_type = 'region'
                    """
                ).fetchall()
                for row in mapped_rows:
                    jurisdiction_uid = row["jurisdiction_uid"] or row["geo_jurisdiction_uid"]
                    mapped_region_meta[row["geo_region_id"]] = {
                        "jurisdiction_uid": jurisdiction_uid or None,
                        "has_region_jurisdiction": bool(row["has_region_jurisdiction"]),
                        "regulation_status": (row["regulation_status"] or "no_regulation").lower(),
                    }
            else:
                region_rows = conn.execute(
                    """
                    SELECT j.country, j.region, r.plant_id
                    FROM regulations r
                    JOIN jurisdictions j ON j.id = r.jurisdiction_id
                    WHERE r.is_webapp_scoped = 1
                      AND j.jurisdiction_type = 'region'
                      AND j.country IS NOT NULL AND TRIM(j.country) != ''
                      AND j.region IS NOT NULL AND TRIM(j.region) != ''
                    """
                ).fetchall()
                for row in region_rows:
                    key = self._region_key(row["country"], row["region"])
                    region_sets[key].add(row["plant_id"])

                status_expr = (
                    "COALESCE(NULLIF(TRIM(j.regulation_status), ''), 'regulated')"
                    if has_status
                    else "'regulated'"
                )
                uid_expr = "COALESCE(NULLIF(TRIM(j.jurisdiction_uid), ''), '')" if has_uid else "''"
                mapped_rows = conn.execute(
                    f"""
                    SELECT
                        j.country,
                        j.region,
                        {uid_expr} AS jurisdiction_uid,
                        {status_expr} AS regulation_status
                    FROM jurisdictions j
                    WHERE j.jurisdiction_type = 'region'
                      AND j.country IS NOT NULL AND TRIM(j.country) != ''
                      AND j.region IS NOT NULL AND TRIM(j.region) != ''
                    """
                ).fetchall()
                for row in mapped_rows:
                    key = self._region_key(row["country"], row["region"])
                    jurisdiction_uid = row["jurisdiction_uid"] or self._fallback_jurisdiction_uid(
                        row["country"], row["region"], "region"
                    )
                    mapped_region_meta[key] = {
                        "jurisdiction_uid": jurisdiction_uid,
                        "has_region_jurisdiction": True,
                        "regulation_status": (row["regulation_status"] or "regulated").lower(),
                    }

            national_sets = defaultdict(set)
            for row in national_rows:
                country = self._canonical_country_name(row["country"])
                national_sets[country].add(row["plant_id"])

            eu_set = {row["plant_id"] for row in eu_rows}

            results = []
            for geo in geo_regions:
                country = self._canonical_country_name(geo["country"])
                region = self._canonical_region_name(geo["region"])
                region_key = (country, region)
                geo_lookup_key = geo["geo_region_id"] if (has_geo_regions and has_uid) else region_key

                selected_sets = []
                count_source_level = "none"

                region_set = region_sets.get(geo_lookup_key, set())
                if include_region and region_set:
                    selected_sets.append(region_set)
                    count_source_level = "region"

                national_set = national_sets.get(country, set())
                if include_national and national_set:
                    selected_sets.append(national_set)
                    if count_source_level == "none":
                        count_source_level = "national"

                international_set = eu_set if (include_international and country in EU_MEMBERS) else set()
                if international_set:
                    selected_sets.append(international_set)
                    if count_source_level == "none":
                        count_source_level = "international"

                if selected_sets:
                    merged = set()
                    for s in selected_sets:
                        merged.update(s)
                    count = len(merged)
                else:
                    count = 0

                mapped_meta = mapped_region_meta.get(geo_lookup_key)
                if mapped_meta and mapped_meta.get("has_region_jurisdiction"):
                    jurisdiction_match = "exact_mapped"
                    regulation_status = mapped_meta.get("regulation_status") or (
                        "regulated" if region_set else "no_regulation"
                    )
                    jurisdiction_uid = (
                        mapped_meta.get("jurisdiction_uid")
                        or geo.get("jurisdiction_uid")
                        or self._fallback_jurisdiction_uid(country, region, "region")
                    )
                elif (has_geo_regions and has_uid) and geo.get("jurisdiction_uid") and (
                    national_set or international_set
                ):
                    jurisdiction_match = "country_overlay"
                    regulation_status = "no_regulation"
                    jurisdiction_uid = geo.get("jurisdiction_uid")
                elif national_set or international_set:
                    jurisdiction_match = "country_overlay"
                    regulation_status = "no_regulation"
                    jurisdiction_uid = self._fallback_jurisdiction_uid(country, region, "region")
                else:
                    jurisdiction_match = "none"
                    regulation_status = "unknown"
                    jurisdiction_uid = self._fallback_jurisdiction_uid(country, region, "region")

                results.append(
                    {
                        "geo_region_id": geo["geo_region_id"],
                        "geojson_slug": geo["geojson_slug"],
                        "country": country,
                        "region": region,
                        "count": count,
                        "count_source_level": count_source_level,
                        "jurisdiction_match": jurisdiction_match,
                        "regulation_status": regulation_status,
                        "jurisdiction_uid": jurisdiction_uid,
                        "canonical_display_name": region if region != country else country,
                    }
                )

            return results
        finally:
            conn.close()

    def get_method_sources(self) -> List[Dict]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                """
                SELECT
                    CASE
                        WHEN j.jurisdiction_type = 'international'
                             AND TRIM(COALESCE(j.jurisdiction_group, '')) != ''
                        THEN j.jurisdiction_group
                        ELSE j.country
                    END AS country,
                    CASE
                        WHEN j.jurisdiction_type = 'national' THEN 'National'
                        WHEN j.jurisdiction_type = 'international'
                        THEN COALESCE(NULLIF(TRIM(j.jurisdiction_group), ''), 'International')
                        WHEN j.jurisdiction_type = 'region' THEN j.region
                        WHEN j.jurisdiction_type = 'habitat' THEN j.region
                        ELSE COALESCE(NULLIF(TRIM(j.region), ''), j.country)
                    END AS name,
                    COALESCE(NULLIF(TRIM(j.authority_name), ''), 'Unknown') AS authority,
                    COALESCE(
                        NULLIF(TRIM(CAST(j.last_updated_year AS TEXT)), ''),
                        NULLIF(TRIM(j.last_updated), ''),
                        'Unknown'
                    ) AS updated,
                    COALESCE(j.methodology_notes, '') AS methodology_notes,
                    COALESCE(j.source_notes, '') AS source_notes
                FROM jurisdictions j
                WHERE EXISTS (
                    SELECT 1
                    FROM regulations r
                    WHERE r.jurisdiction_id = j.id
                )
                ORDER BY country ASC, j.jurisdiction_type ASC, name ASC
                """
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
