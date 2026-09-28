#!/usr/bin/env python3
import argparse
import os
import sqlite3
from collections import defaultdict


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_regions_by_country(conn: sqlite3.Connection) -> dict[str, list[str]]:
    rows = conn.execute(
        """
        SELECT country, region
        FROM regions_country
        WHERE country IS NOT NULL AND TRIM(country) != ''
          AND region IS NOT NULL AND TRIM(region) != ''
        ORDER BY country, region
        """
    ).fetchall()

    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        grouped[row["country"]].append(row["region"])
    return grouped


def print_section(title: str):
    print()
    print(title)
    print("-" * len(title))


def print_rows(rows, columns):
    if not rows:
        print("None")
        return

    widths = {}
    for column in columns:
        widths[column] = max(len(column), *(len(str(row[column] or "")) for row in rows))

    header = " | ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("-+-".join("-" * widths[column] for column in columns))
    for row in rows:
        print(" | ".join(str(row[column] or "").ljust(widths[column]) for column in columns))


def main():
    parser = argparse.ArgumentParser(
        description="Audit jurisdiction rows for likely national/state classification issues."
    )
    parser.add_argument("db_path", help="Path to weeds.db")
    parser.add_argument(
        "--country",
        help="Optional country to inspect in more detail, e.g. 'United States'",
    )
    args = parser.parse_args()

    db_path = os.path.abspath(args.db_path)
    if not os.path.exists(db_path):
        raise SystemExit(f"Database not found: {db_path}")

    conn = connect(db_path)
    try:
        print(f"Database: {db_path}")

        print_section("National rows with a non-empty region")
        national_with_region = conn.execute(
            """
            SELECT
                j.id,
                j.country,
                j.region,
                j.boundary_level,
                COALESCE(NULLIF(TRIM(j.authority_name), ''), 'Unknown') AS authority_name,
                COUNT(DISTINCT r.plant_id) AS plant_count
            FROM jurisdictions j
            LEFT JOIN regulations r
              ON r.jurisdiction_id = j.id
             AND r.is_webapp_scoped = 1
            WHERE j.jurisdiction_type = 'national'
              AND j.region IS NOT NULL
              AND TRIM(j.region) != ''
            GROUP BY j.id, j.country, j.region, j.boundary_level, j.authority_name
            ORDER BY j.country, j.region, authority_name
            """
        ).fetchall()
        print_rows(
            national_with_region,
            ["id", "country", "region", "boundary_level", "authority_name", "plant_count"],
        )

        print_section("Countries with multiple blank-region national rows")
        multiple_national_rows = conn.execute(
            """
            SELECT
                j.country,
                COUNT(*) AS national_row_count,
                SUM(plant_count) AS total_plants
            FROM (
                SELECT
                    j.id,
                    j.country,
                    COUNT(DISTINCT r.plant_id) AS plant_count
                FROM jurisdictions j
                LEFT JOIN regulations r
                  ON r.jurisdiction_id = j.id
                 AND r.is_webapp_scoped = 1
                WHERE j.jurisdiction_type = 'national'
                  AND (j.region IS NULL OR TRIM(j.region) = '')
                GROUP BY j.id, j.country
            ) j
            GROUP BY j.country
            HAVING COUNT(*) > 1
            ORDER BY national_row_count DESC, j.country
            """
        ).fetchall()
        print_rows(multiple_national_rows, ["country", "national_row_count", "total_plants"])

        print_section("Blank-region national rows whose authority mentions a region name")
        regions_by_country = fetch_regions_by_country(conn)
        national_rows = conn.execute(
            """
            SELECT
                j.id,
                j.country,
                COALESCE(NULLIF(TRIM(j.authority_name), ''), 'Unknown') AS authority_name,
                j.boundary_level,
                COUNT(DISTINCT r.plant_id) AS plant_count
            FROM jurisdictions j
            LEFT JOIN regulations r
              ON r.jurisdiction_id = j.id
             AND r.is_webapp_scoped = 1
            WHERE j.jurisdiction_type = 'national'
              AND (j.region IS NULL OR TRIM(j.region) = '')
            GROUP BY j.id, j.country, j.authority_name, j.boundary_level
            ORDER BY j.country, authority_name
            """
        ).fetchall()

        suspicious = []
        for row in national_rows:
            country = row["country"]
            authority_name = (row["authority_name"] or "").lower()
            for region in regions_by_country.get(country, []):
                if region.lower() in authority_name:
                    suspicious.append(
                        {
                            "id": row["id"],
                            "country": country,
                            "matched_region": region,
                            "boundary_level": row["boundary_level"],
                            "authority_name": row["authority_name"],
                            "plant_count": row["plant_count"],
                        }
                    )
                    break

        print_rows(
            suspicious,
            ["id", "country", "matched_region", "boundary_level", "authority_name", "plant_count"],
        )

        if args.country:
            print_section(f"Jurisdictions for {args.country}")
            country_rows = conn.execute(
                """
                SELECT
                    j.id,
                    j.jurisdiction_type,
                    COALESCE(NULLIF(TRIM(j.region), ''), '') AS region,
                    j.boundary_level,
                    COALESCE(NULLIF(TRIM(j.authority_name), ''), 'Unknown') AS authority_name,
                    COUNT(DISTINCT r.plant_id) AS plant_count
                FROM jurisdictions j
                LEFT JOIN regulations r
                  ON r.jurisdiction_id = j.id
                 AND r.is_webapp_scoped = 1
                WHERE j.country = ?
                GROUP BY j.id, j.jurisdiction_type, j.region, j.boundary_level, j.authority_name
                ORDER BY j.jurisdiction_type, region, authority_name
                """,
                (args.country,),
            ).fetchall()
            print_rows(
                country_rows,
                ["id", "jurisdiction_type", "region", "boundary_level", "authority_name", "plant_count"],
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
