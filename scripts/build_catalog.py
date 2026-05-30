import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "catalog"

TABLES_SQL = """
SELECT schema_name, table_name, description, required_filters
FROM coral.tables
ORDER BY schema_name, table_name
""".strip()

COLUMNS_SQL = """
SELECT
  schema_name,
  table_name,
  ordinal_position,
  column_name,
  data_type,
  is_nullable,
  is_virtual,
  is_required_filter,
  description,
  filter_mode
FROM coral.columns
ORDER BY schema_name, table_name, ordinal_position
""".strip()

FILTERS_SQL = """
SELECT
  schema_name,
  table_name,
  filter_name,
  is_required,
  filter_mode,
  data_type,
  description
FROM coral.filters
ORDER BY schema_name, table_name, filter_name
""".strip()

OUTPUT_PATH = CATALOG_DIR / "raw_catalog.json"
OPERATIONAL_JOIN_KEYS = {"related_pr"}


def run_coral_json(sql):
    result = subprocess.run(
        ["coral", "sql", "--format", "json", sql],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return json.loads(result.stdout)


def group_by_source_table(rows):
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["schema_name"]][row["table_name"]].append(row)
    return grouped


def is_promoted_join_key(column_name):
    return (
        column_name == "id"
        or column_name.endswith("_id")
        or column_name.endswith("_pr")
        or column_name in OPERATIONAL_JOIN_KEYS
    )


def detect_join_candidates(tables):
    column_tables = defaultdict(list)

    for table in tables:
        for column in table["columns"]:
            if column["virtual"]:
                continue
            column_tables[column["name"]].append(
                {
                    "table": table["name"],
                    "type": column["type"],
                }
            )

    candidates = []
    for column_name, occurrences in sorted(column_tables.items()):
        all_occurrences = list(occurrences)
        if column_name.endswith("_pr") and "pr_number" in column_tables:
            existing_tables = {occurrence["table"] for occurrence in all_occurrences}
            all_occurrences.extend(
                {
                    "table": occurrence["table"],
                    "type": occurrence["type"],
                    "column": "pr_number",
                }
                for occurrence in column_tables["pr_number"]
                if occurrence["table"] not in existing_tables
            )

        participating_tables = sorted({occurrence["table"] for occurrence in all_occurrences})
        if len(participating_tables) < 2:
            continue

        type_counts = Counter(occurrence["type"] for occurrence in all_occurrences)
        candidates.append(
            {
                "column": column_name,
                "promoted": is_promoted_join_key(column_name),
                "tables": [
                    {
                        "name": table_name,
                        "columns": sorted(
                            {
                                occurrence.get("column", column_name)
                                for occurrence in all_occurrences
                                if occurrence["table"] == table_name
                            }
                        ),
                        "types": sorted(
                            {
                                occurrence["type"]
                                for occurrence in all_occurrences
                                if occurrence["table"] == table_name
                            }
                        ),
                    }
                    for table_name in participating_tables
                ],
                "types": dict(sorted(type_counts.items())),
            }
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            not candidate["promoted"],
            candidate["column"],
        ),
    )


def attach_table_join_candidates(tables, source_join_candidates):
    candidates_by_table = defaultdict(list)
    for candidate in source_join_candidates:
        table_names = {table["name"] for table in candidate["tables"]}
        for table_name in table_names:
            candidates_by_table[table_name].append(
                {
                    "column": candidate["column"],
                    "promoted": candidate["promoted"],
                    "joins_with": sorted(table_names - {table_name}),
                    "types": candidate["types"],
                }
            )

    for table in tables:
        table["join_candidates"] = candidates_by_table[table["name"]]


def build_catalog():
    table_rows = run_coral_json(TABLES_SQL)
    column_rows = run_coral_json(COLUMNS_SQL)
    filter_rows = run_coral_json(FILTERS_SQL)

    columns_by_table = group_by_source_table(column_rows)
    filters_by_table = group_by_source_table(filter_rows)

    sources = defaultdict(list)
    for table_row in table_rows:
        schema_name = table_row["schema_name"]
        table_name = table_row["table_name"]

        columns = [
            {
                "name": column["column_name"],
                "type": column["data_type"],
                "nullable": column["is_nullable"],
                "virtual": column["is_virtual"],
                "required_filter": column["is_required_filter"],
                "description": column["description"] or "",
                "filter_mode": column["filter_mode"],
            }
            for column in columns_by_table[schema_name][table_name]
        ]

        filters = [
            {
                "name": filter_row["filter_name"],
                "required": filter_row["is_required"],
                "filter_mode": filter_row["filter_mode"],
                "type": filter_row["data_type"],
                "description": filter_row["description"] or "",
            }
            for filter_row in filters_by_table[schema_name][table_name]
        ]

        sources[schema_name].append(
            {
                "name": table_name,
                "description": table_row["description"] or "",
                "required_filters": table_row["required_filters"] or "",
                "columns": columns,
                "filters": filters,
                "join_candidates": [],
            }
        )

    catalog_sources = []
    for source_name in sorted(sources):
        tables = sorted(sources[source_name], key=lambda table: table["name"])
        join_candidates = detect_join_candidates(tables)
        attach_table_join_candidates(tables, join_candidates)

        catalog_sources.append(
            {
                "name": source_name,
                "table_count": len(tables),
                "tables": tables,
                "join_candidates": join_candidates,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": catalog_sources,
    }


def main():
    catalog = build_catalog()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(catalog, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    source_count = len(catalog["sources"])
    table_count = sum(source["table_count"] for source in catalog["sources"])
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Sources: {source_count}")
    print(f"Tables: {table_count}")


if __name__ == "__main__":
    main()
