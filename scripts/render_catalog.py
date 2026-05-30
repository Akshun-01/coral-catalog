import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "catalog"

ANNOTATED_PATH = CATALOG_DIR / "annotated_catalog.json"
CATALOG_MD_PATH = CATALOG_DIR / "catalog.md"
CATALOG_JSON_PATH = CATALOG_DIR / "catalog.json"
CATALOG_SKILL_PATH = CATALOG_DIR / "catalog_skill.md"


def estimate_tokens(text):
    return int(len(text) * 0.75)


def load_annotated_catalog():
    return json.loads(ANNOTATED_PATH.read_text(encoding="utf-8"))


def column_lookup(table):
    return {column["name"]: column for column in table.get("columns", [])}


def render_table(table):
    lookup = column_lookup(table)
    important_columns = table.get("important_columns") or [
        column["name"] for column in table.get("columns", [])[:4]
    ]
    rendered_columns = []
    for column_name in important_columns:
        column = lookup.get(column_name)
        if column:
            rendered_columns.append(f"{column_name} ({column['type']})")
        else:
            rendered_columns.append(column_name)

    lines = [f"**{table['name']}** - {table['description']}"]
    if rendered_columns:
        lines.append("Cols: " + ", ".join(rendered_columns))
    if table.get("required_filters"):
        lines.append("Required filters: " + ", ".join(table["required_filters"]))
    return "\n".join(lines)


def render_source(source):
    backend = "jsonl" if source["name"] == "ops_incident_demo" else "http"
    is_incident = source["name"] == "ops_incident_demo"
    lines = [
        f"## {source['name']}  ({backend})",
        "",
        source["source_description"],
        "",
        "### Joins",
        compact_join_text(source["join_explanation"] or "No repeated join keys detected."),
        "",
        "### Tables",
        "",
    ]

    for table in source["tables"]:
        lines.append(render_table(table))
        lines.append("")

    if source.get("compressed") and source.get("remaining_tables"):
        remaining = ", ".join(source["remaining_tables"])
        lines.append(f"Additional tables summarized by name: {remaining}")
        lines.append("")

    if is_incident:
        lines = [line for line in lines if line != ""]

    if source.get("example_queries"):
        lines.append("### Query")
        if not is_incident:
            lines.append("")
        for query in source["example_queries"]:
            lines.append("```sql")
            lines.append(compact_sql(query))
            lines.append("```")
            if not is_incident:
                lines.append("")

    return "\n".join(lines).rstrip()


def compact_sql(query):
    return " ".join(query.split())


def compact_join_text(text):
    return text.replace("deployment_id", "`deployment_id`").replace(
        "incident_id", "`incident_id`"
    ).replace("related_pr", "`related_pr`")


def render_markdown(catalog):
    source_count = len(catalog["sources"])
    table_count = sum(source["table_count"] for source in catalog["sources"])
    generated = datetime.now(timezone.utc).isoformat()

    body_parts = [render_source(source) for source in catalog["sources"]]
    body = "\n\n---\n\n".join(body_parts)
    token_count = estimate_tokens(body)

    header = "\n".join(
        [
            "# Coral Schema Catalog",
            f"Generated: {generated}",
            f"Sources: {source_count}  Tables: {table_count}  Estimated tokens: {token_count}",
            "",
            "---",
            "",
        ]
    )
    return header + body + "\n"


def clean_json(catalog):
    return {
        "sources": [
            {
                "name": source["name"],
                "description": source["source_description"],
                "table_count": source["table_count"],
                "join_hints": source.get("join_candidates", []),
                "join_explanation": source.get("join_explanation", ""),
                "tables": [
                    {
                        "name": table["name"],
                        "description": table["description"],
                        "columns": table.get("columns", []),
                        "required_filters": table.get("required_filters", []),
                        "filters": table.get("filters", []),
                        "join_hints": table.get("join_candidates", []),
                    }
                    for table in source.get("tables", [])
                ],
                "compressed": source.get("compressed", False),
                "remaining_tables": source.get("remaining_tables", []),
                "example_queries": source.get("example_queries", []),
            }
            for source in catalog["sources"]
        ]
    }


def render_skill():
    return """# Coral Catalog Skill

The file `catalog.md` in this directory contains a pre-built schema catalog for all connected Coral sources.

## Instructions for agents

1. At the start of any task that involves querying Coral data, read `catalog.md` first.
2. Use the catalog to identify which tables and join keys are relevant to the task.
3. Do NOT call `list_catalog` or `describe_table` for sources that appear in `catalog.md` - the catalog already contains this information.
4. If the catalog does not contain a source you need, fall back to `list_catalog` and `describe_table` as normal.
5. The catalog may be outdated if sources were recently added or removed. If a query fails because a table does not exist, run `coral catalog build` to rebuild, then retry.

## When to rebuild

Run `coral catalog build` when:
- A new source is added with `coral source add`
- A source is removed
- A source spec is updated

The catalog is stable otherwise. Treat it like a Docker layer: build once, reuse until a source changes.
"""


def main():
    catalog = load_annotated_catalog()
    markdown = render_markdown(catalog)
    clean = clean_json(catalog)
    skill = render_skill()

    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_MD_PATH.write_text(markdown, encoding="utf-8")
    CATALOG_JSON_PATH.write_text(
        json.dumps(clean, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    CATALOG_SKILL_PATH.write_text(skill, encoding="utf-8")

    print(f"Wrote {CATALOG_MD_PATH}")
    print(f"Wrote {CATALOG_JSON_PATH}")
    print(f"Wrote {CATALOG_SKILL_PATH}")
    print(f"Estimated catalog.md tokens: {estimate_tokens(markdown)}")


if __name__ == "__main__":
    main()
