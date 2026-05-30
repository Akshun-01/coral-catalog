import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "catalog"

RAW_PATH = CATALOG_DIR / "raw_catalog.json"
OUTPUT_PATH = CATALOG_DIR / "annotated_catalog.json"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
SOURCE_TOKEN_BUDGET = 800


def estimate_tokens(text):
    return int(len(text) * 0.75)


def load_raw_catalog():
    return json.loads(RAW_PATH.read_text(encoding="utf-8"))


def source_prompt_payload(source):
    tables = []
    sorted_tables = sorted(
        source["tables"], key=lambda table: len(table["columns"]), reverse=True
    )
    selected_tables = sorted_tables[:15] if len(sorted_tables) > 30 else sorted_tables

    for table in selected_tables:
        tables.append(
            {
                "name": table["name"],
                "description": table["description"],
                "columns": [
                    {
                        "name": column["name"],
                        "type": column["type"],
                        "required_filter": column["required_filter"],
                    }
                    for column in table["columns"]
                ],
                "filters": table["filters"],
            }
        )

    payload = {
        "name": source["name"],
        "table_count": source["table_count"],
        "tables": tables,
        "remaining_tables": [
            table["name"] for table in sorted_tables[15:]
        ]
        if len(sorted_tables) > 30
        else [],
        "join_keys": source["join_candidates"][:50],
    }
    return payload


def build_prompt(source):
    payload = source_prompt_payload(source)
    return f"""
You are annotating a database schema for use by an AI agent.
The agent will use this annotation to understand what data is available and how to query it.
Write concise, precise descriptions. Avoid filler phrases. Focus on what an agent needs to know to write SQL.

Source name: {source["name"]}
Tables and columns: {json.dumps(payload, indent=2)}

Produce output as JSON matching this schema:
{{
  "source_description": "...",
  "tables": [
    {{
      "name": "...",
      "description": "...",
      "important_columns": ["col1", "col2"],
      "required_filters": ["col = value"]
    }}
  ],
  "join_explanation": "...",
  "example_queries": ["SELECT ...", "SELECT ..."]
}}
Return only valid JSON. No markdown fences. No preamble.
""".strip()


def call_claude(source, api_key, model):
    request_body = {
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": build_prompt(source)}],
    }
    request = urllib.request.Request(
        ANTHROPIC_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))

    content = payload["content"][0]["text"]
    return json.loads(content)


def important_columns(table):
    columns = table["columns"]
    important = []
    for column in columns:
        name = column["name"]
        if (
            column["required_filter"]
            or name in {"id", "pr_number", "related_pr", "deployment_id", "incident_id"}
            or name.endswith("_id")
            or name.endswith("_pr")
        ):
            important.append(name)

    for column in columns:
        if len(important) >= 2:
            break
        if column["name"] not in important:
            important.append(column["name"])
    return important


def required_filter_expressions(table):
    expressions = []
    for filter_row in table["filters"]:
        if filter_row["required"]:
            expressions.append(f"{filter_row['name']} = <value>")
    return expressions


def join_explanation(source):
    candidate_names = {candidate["column"] for candidate in source["join_candidates"]}
    table_names = {table["name"] for table in source["tables"]}
    if {"related_pr", "deployment_id", "incident_id"}.issubset(
        candidate_names
    ) and {
        "github_prs",
        "deployments",
        "incidents",
        "sentry_events",
        "support_tickets",
    }.issubset(table_names):
        return (
            "Join PR -> deployment by related_pr, deployment -> incident by deployment_id, then incident_id to errors/tickets/Slack."
        )

    promoted = [
        candidate
        for candidate in source["join_candidates"]
        if candidate["promoted"]
    ]
    if not promoted:
        return "No repeated identifier-like columns were detected across tables in this source."

    parts = []
    for candidate in promoted[:5]:
        tables = []
        for table in candidate["tables"]:
            columns = table.get("columns") or [candidate["column"]]
            if columns == [candidate["column"]]:
                tables.append(table["name"])
            else:
                tables.append(f"{table['name']} ({'/'.join(columns)})")
        parts.append(f"{candidate['column']} links {', '.join(tables)}")
    return "; ".join(parts) + "."


def table_description(table):
    compact_descriptions = {
        "github_prs": "PRs.",
        "deployments": "Deployments.",
        "incidents": "Incidents.",
        "sentry_events": "Errors.",
        "support_tickets": "Tickets.",
        "slack_messages": "Slack.",
    }
    if table["name"] in compact_descriptions:
        return compact_descriptions[table["name"]]
    if table["description"]:
        return table["description"].rstrip(".") + "."
    column_names = [column["name"] for column in table["columns"][:3]]
    return f"{table['name']} records with columns such as {', '.join(column_names)}."


def source_description(source):
    names = {table["name"] for table in source["tables"]}
    if {
        "github_prs",
        "deployments",
        "incidents",
        "sentry_events",
        "support_tickets",
    }.issubset(names):
        return (
            "Incident demo: PRs, deploys, errors, tickets."
        )
    if source["table_count"] > 30:
        return (
            f"{source['name']} exposes {source['table_count']} API-backed tables. "
            "Use required filters before querying provider tables, then join repeated identifier columns where available."
        )
    return (
        f"{source['name']} contains {source['table_count']} related tables. "
        "Use the listed join keys and required filters to build Coral SQL queries."
    )


def incident_queries(source):
    names = {table["name"] for table in source["tables"]}
    if not {
        "github_prs",
        "deployments",
        "incidents",
        "sentry_events",
        "support_tickets",
        "slack_messages",
    }.issubset(names):
        return []

    schema = source["name"]
    return [
        (
            "SELECT p.pr_number,count(DISTINCT s.event_id) errors,count(DISTINCT t.ticket_id) tickets "
            f"FROM {schema}.github_prs p "
            f"JOIN {schema}.deployments d ON d.related_pr=p.pr_number "
            f"JOIN {schema}.incidents i ON i.deployment_id=d.deployment_id "
            f"JOIN {schema}.sentry_events s ON s.incident_id=i.incident_id "
            f"JOIN {schema}.support_tickets t ON t.incident_id=i.incident_id "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
        ),
    ]


def generic_example_queries(source):
    incident = incident_queries(source)
    if incident:
        return incident

    for candidate in source["join_candidates"]:
        if len(candidate["tables"]) < 2:
            continue
        left = candidate["tables"][0]
        right = candidate["tables"][1]
        left_column = (left.get("columns") or [candidate["column"]])[0]
        right_column = (right.get("columns") or [candidate["column"]])[0]
        return [
            (
                f"SELECT *\n"
                f"FROM {source['name']}.{left['name']} a\n"
                f"JOIN {source['name']}.{right['name']} b ON b.{right_column} = a.{left_column}\n"
                f"LIMIT 20"
            )
        ]

    if source["tables"]:
        table = source["tables"][0]
        where = ""
        required = required_filter_expressions(table)
        if required:
            where = "\nWHERE " + " AND ".join(required)
        return [f"SELECT *\nFROM {source['name']}.{table['name']}{where}\nLIMIT 20"]
    return []


def local_annotation(source):
    selected_tables = source["tables"]
    remaining_tables = []
    compressed = False
    if source["table_count"] > 30:
        selected_tables = sorted(
            source["tables"], key=lambda table: len(table["columns"]), reverse=True
        )[:15]
        selected_names = {table["name"] for table in selected_tables}
        remaining_tables = [
            table["name"] for table in source["tables"] if table["name"] not in selected_names
        ]
        compressed = True

    annotation = {
        "source_description": source_description(source),
        "tables": [
            {
                "name": table["name"],
                "description": table_description(table),
                "important_columns": important_columns(table),
                "required_filters": required_filter_expressions(table),
            }
            for table in selected_tables
        ],
        "join_explanation": join_explanation(source),
        "example_queries": generic_example_queries(source),
    }
    if compressed:
        annotation["compressed"] = True
        annotation["remaining_tables"] = remaining_tables
    return annotation


def normalize_annotation(source, annotation):
    table_by_name = {table["name"]: table for table in source["tables"]}
    normalized_tables = []
    for table_annotation in annotation.get("tables", []):
        name = table_annotation["name"]
        raw_table = table_by_name.get(name)
        normalized_tables.append(
            {
                "name": name,
                "description": table_annotation.get("description", "").strip(),
                "important_columns": table_annotation.get("important_columns", []),
                "required_filters": table_annotation.get("required_filters", []),
                "columns": raw_table["columns"] if raw_table else [],
                "filters": raw_table["filters"] if raw_table else [],
                "join_candidates": raw_table["join_candidates"] if raw_table else [],
            }
        )

    return {
        "name": source["name"],
        "table_count": source["table_count"],
        "source_description": annotation.get("source_description", "").strip(),
        "tables": normalized_tables,
        "join_explanation": annotation.get("join_explanation", "").strip(),
        "example_queries": annotation.get("example_queries", []),
        "join_candidates": source["join_candidates"],
        "compressed": annotation.get("compressed", False),
        "remaining_tables": annotation.get("remaining_tables", []),
    }


def markdown_preview(source_annotation):
    lines = [
        f"## {source_annotation['name']}",
        source_annotation["source_description"],
        "### Join Relationships",
        source_annotation["join_explanation"],
        "### Tables",
    ]
    for table in source_annotation["tables"]:
        lines.append(f"**{table['name']}** - {table['description']}")
        lines.append("Columns: " + ", ".join(table["important_columns"]))
        if table["required_filters"]:
            lines.append("Required filters: " + ", ".join(table["required_filters"]))
    for query in source_annotation["example_queries"]:
        lines.append(query)
    return "\n".join(lines)


def compress_if_needed(source_annotation):
    estimated = estimate_tokens(markdown_preview(source_annotation))
    source_annotation["estimated_tokens"] = estimated
    if estimated <= SOURCE_TOKEN_BUDGET:
        return

    source_annotation["compressed"] = True
    source_annotation["example_queries"] = source_annotation["example_queries"][:1]
    for table in source_annotation["tables"]:
        table["important_columns"] = table["important_columns"][:1]
        words = table["description"].split()
        if len(words) > 8:
            table["description"] = " ".join(words[:8]).rstrip(".") + "."

    retained = source_annotation["tables"][:15]
    retained_names = {table["name"] for table in retained}
    source_annotation["remaining_tables"] = source_annotation.get(
        "remaining_tables", []
    ) + [
        table["name"]
        for table in source_annotation["tables"]
        if table["name"] not in retained_names
    ]
    source_annotation["tables"] = retained
    source_annotation["estimated_tokens"] = estimate_tokens(
        markdown_preview(source_annotation)
    )


def annotate_catalog(use_claude=True):
    raw_catalog = load_raw_catalog()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
    annotations = []
    annotation_mode = "local"

    for source in raw_catalog["sources"]:
        annotation = None
        if use_claude and api_key:
            try:
                annotation = call_claude(source, api_key, model)
                annotation_mode = "claude"
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                print(
                    f"Claude annotation failed for {source['name']}: {error}; using local annotation.",
                    file=sys.stderr,
                )
        if annotation is None:
            annotation = local_annotation(source)

        normalized = normalize_annotation(source, annotation)
        compress_if_needed(normalized)
        annotations.append(normalized)

    return {
        "generated_from": str(RAW_PATH),
        "annotation_mode": annotation_mode,
        "sources": annotations,
    }


def main():
    use_claude = "--no-claude" not in sys.argv
    annotated = annotate_catalog(use_claude=use_claude)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(annotated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")
    print(f"Annotation mode: {annotated['annotation_mode']}")
    for source in annotated["sources"]:
        print(
            f"{source['name']}: {source['table_count']} tables, "
            f"{source['estimated_tokens']} estimated tokens"
        )


if __name__ == "__main__":
    main()
