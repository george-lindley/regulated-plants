from typing import Dict, List
from app.utils.database_base import DatabaseBase


class SpeciesDatabase(DatabaseBase):
    """Species search and per-species jurisdiction lookups."""

    def __init__(self, db_path: str = "weeds.db", geojson_dir: str = None):
        super().__init__(db_path=db_path, geojson_dir=geojson_dir)

    @staticmethod
    def _primary_common_name(value: str, fallback: str = None) -> str:
        raw = (value or "").strip()
        if not raw:
            return fallback
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        return parts[0] if parts else (fallback or raw)

    def get_all_weeds(self) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT
                    p.species_id,
                    p.gbif_usage_key AS usage_key,
                    p.canonical_name,
                    COALESCE(NULLIF(TRIM(p.english_name), ''), p.canonical_name) AS common_name,
                    p.family_name,
                    p.synonyms,
                    j.country,
                    j.region,
                    j.jurisdiction_type AS jurisdiction,
                    j.jurisdiction_group,
                    r.classification,
                    r.note
                FROM regulations r
                JOIN plants p ON p.id = r.plant_id
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                ORDER BY j.country, j.jurisdiction_type, j.region, p.canonical_name
                """
            )
            results = [dict(row) for row in cursor.fetchall()]
            for row in results:
                row["common_name"] = self._primary_common_name(
                    row.get("common_name"),
                    row.get("canonical_name"),
                )
            return results
        finally:
            conn.close()

    def search_weeds(self, query: str) -> List[Dict]:
        query = (query or "").strip().lower()
        if not query:
            return []

        conn = self.get_connection()
        try:
            exact_match = query
            starts_with = f"{query}%"
            contains = f"%{query}%"

            cursor = conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(TRIM(p.english_name), ''), p.canonical_name) AS common_name,
                    p.species_id,
                    p.canonical_name,
                    p.family_name,
                    p.synonyms,
                    p.gbif_usage_key AS usage_key,
                    p.lifeform_final,
                    p.lifespan_final,
                    p.habitat_final,
                    p.woodiness_final,
                    CASE
                        WHEN LOWER(COALESCE(p.english_name, '')) = ? OR LOWER(p.canonical_name) = ? THEN 3
                        WHEN LOWER(COALESCE(p.english_name, '')) LIKE ? OR LOWER(p.canonical_name) LIKE ? THEN 2
                        ELSE 1
                    END AS search_priority
                FROM plants p
                WHERE p.has_current_regulation = 1
                  AND (
                      LOWER(COALESCE(p.english_name, '')) LIKE ?
                      OR LOWER(p.canonical_name) LIKE ?
                      OR LOWER(COALESCE(p.synonyms, '')) LIKE ?
                  )
                ORDER BY search_priority DESC, common_name ASC
                LIMIT 20
                """,
                (
                    exact_match,
                    exact_match,
                    starts_with,
                    starts_with,
                    contains,
                    contains,
                    contains,
                ),
            )
            results = [dict(row) for row in cursor.fetchall()]
            for row in results:
                row["common_name"] = self._primary_common_name(
                    row.get("common_name"),
                    row.get("canonical_name"),
                )
            return results
        finally:
            conn.close()

    def get_species_by_id(self, species_id: str) -> Dict:
        conn = self.get_connection()
        try:
            row = conn.execute(
                """
                SELECT
                    COALESCE(NULLIF(TRIM(p.english_name), ''), p.canonical_name) AS common_name,
                    p.species_id,
                    p.canonical_name,
                    p.family_name,
                    p.synonyms,
                    p.gbif_usage_key AS usage_key,
                    p.lifeform_final,
                    p.lifespan_final,
                    p.habitat_final,
                    p.woodiness_final
                FROM plants p
                WHERE p.species_id = ?
                  AND p.has_current_regulation = 1
                LIMIT 1
                """,
                (species_id,),
            ).fetchone()
            if not row:
                return {}
            result = dict(row)
            result["common_name"] = self._primary_common_name(
                result.get("common_name"),
                result.get("canonical_name"),
            )
            return result
        finally:
            conn.close()

    def get_weeds_by_usage_key(self, usage_key: int) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT
                    p.species_id,
                    p.gbif_usage_key AS usage_key,
                    p.canonical_name,
                    COALESCE(NULLIF(TRIM(p.english_name), ''), p.canonical_name) AS common_name,
                    p.family_name,
                    p.synonyms,
                    j.country,
                    j.region,
                    j.jurisdiction_type AS jurisdiction,
                    j.jurisdiction_group,
                    r.classification,
                    r.note
                FROM regulations r
                JOIN plants p ON p.id = r.plant_id
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE p.gbif_usage_key = ?
                  AND r.is_webapp_scoped = 1
                ORDER BY j.country, j.jurisdiction_type, j.region
                """,
                (usage_key,),
            )
            results = [dict(row) for row in cursor.fetchall()]
            for row in results:
                row["common_name"] = self._primary_common_name(
                    row.get("common_name"),
                    row.get("canonical_name"),
                )
            return results
        finally:
            conn.close()

    def get_weeds_by_species_id(self, species_id: str) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT
                    p.species_id,
                    p.gbif_usage_key AS usage_key,
                    p.canonical_name,
                    COALESCE(NULLIF(TRIM(p.english_name), ''), p.canonical_name) AS common_name,
                    p.family_name,
                    p.synonyms,
                    j.country,
                    j.region,
                    j.jurisdiction_type AS jurisdiction,
                    j.jurisdiction_group,
                    r.classification,
                    r.note
                FROM regulations r
                JOIN plants p ON p.id = r.plant_id
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE p.species_id = ?
                  AND r.is_webapp_scoped = 1
                ORDER BY j.country, j.jurisdiction_type, j.region
                """,
                (species_id,),
            )
            results = [dict(row) for row in cursor.fetchall()]
            for row in results:
                row["common_name"] = self._primary_common_name(
                    row.get("common_name"),
                    row.get("canonical_name"),
                )
            return results
        finally:
            conn.close()

    def get_states_by_weed(self, weed_name: str) -> List[str]:
        conn = self.get_connection()
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT
                    j.region,
                    j.country,
                    j.jurisdiction_type AS jurisdiction
                FROM regulations r
                JOIN plants p ON p.id = r.plant_id
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE r.is_webapp_scoped = 1
                  AND (
                      LOWER(COALESCE(p.english_name, '')) = LOWER(?)
                      OR LOWER(p.canonical_name) = LOWER(?)
                  )
                ORDER BY j.country, j.jurisdiction_type, j.region
                """,
                (weed_name, weed_name),
            ).fetchall()

            formatted = []
            for row in rows:
                country = row["country"]
                jurisdiction = row["jurisdiction"]
                region = row["region"]

                if jurisdiction == "national":
                    formatted.append(f"National ({country})")
                elif jurisdiction == "international":
                    formatted.append(f"International ({country})")
                elif region:
                    formatted.append(region)

            seen = set()
            out = []
            for item in formatted:
                if item not in seen:
                    out.append(item)
                    seen.add(item)
            return out
        finally:
            conn.close()

    def _get_states_by_plant_column(self, column: str, value) -> Dict[str, List[str]]:
        if column not in {"species_id", "gbif_usage_key"}:
            raise ValueError(f"Unsupported plant lookup column: {column}")

        conn = self.get_connection()
        try:
            cursor = conn.execute(
                f"""
                SELECT DISTINCT
                    CASE
                        WHEN j.jurisdiction_type = 'international'
                             AND TRIM(COALESCE(j.jurisdiction_group, '')) != ''
                        THEN j.jurisdiction_group
                        ELSE j.country
                    END AS country_key,
                    j.jurisdiction_type AS jurisdiction,
                    j.region
                FROM regulations r
                JOIN plants p ON p.id = r.plant_id
                JOIN jurisdictions j ON j.id = r.jurisdiction_id
                WHERE p.{column} = ?
                  AND r.is_webapp_scoped = 1
                ORDER BY country_key, jurisdiction, region
                """,
                (value,),
            )
            results = cursor.fetchall()

            regulations_by_country: Dict[str, List[str]] = {}
            for row in results:
                country = row["country_key"]
                jurisdiction = row["jurisdiction"]
                region = row["region"]

                if not country:
                    continue

                if country not in regulations_by_country:
                    regulations_by_country[country] = []

                if jurisdiction == "national":
                    if "National Level" not in regulations_by_country[country]:
                        regulations_by_country[country].append("National Level")
                elif jurisdiction == "international":
                    if "International Level" not in regulations_by_country[country]:
                        regulations_by_country[country].append("International Level")
                elif jurisdiction == "region" and region:
                    if region not in regulations_by_country[country]:
                        regulations_by_country[country].append(region)

            return regulations_by_country
        finally:
            conn.close()

    def get_states_by_species_id(self, species_id: str) -> Dict[str, List[str]]:
        return self._get_states_by_plant_column("species_id", species_id)

    def get_states_by_usage_key(self, usage_key: int) -> Dict[str, List[str]]:
        return self._get_states_by_plant_column("gbif_usage_key", usage_key)
