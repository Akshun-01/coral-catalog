import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = ROOT / "catalog"

RAW_PATH = CATALOG_DIR / "raw_catalog.json"
OUT_DIR = ROOT / "optimized_catalog"
SOURCE_DIR = OUT_DIR / "sources"
INDEX_MD = OUT_DIR / "catalog_index.md"
INDEX_JSON = OUT_DIR / "catalog_index.json"
RECIPES_JSON = OUT_DIR / "query_recipes.json"
SKILL_MD = OUT_DIR / "catalog_optimized_skill.md"

HIGH_VALUE_GITHUB_TABLES = [
    "repos_get",
    "pulls",
    "issues",
    "repo_issue_events",
    "timeline",
    "repo_action_runs",
    "repo_action_workflow_runs",
    "repo_commits",
    "repo_pull_comments",
    "repo_pull_review_comments",
    "repo_deployments",
    "repo_deployment_statuses",
]

OPS_TABLE_COLUMNS = {
    "github_prs": ["pr_number", "author", "deployment_id", "reverts_pr", "fixes_pr"],
    "deployments": ["deployment_id", "related_pr", "deployed_at", "status"],
    "incidents": ["incident_id", "deployment_id", "related_pr", "severity"],
    "sentry_events": ["event_id", "incident_id", "error_type", "tenant"],
    "support_tickets": ["ticket_id", "incident_id", "plan", "severity"],
    "slack_messages": ["timestamp", "incident_id", "user", "message"],
}


def estimate_tokens(text):
    return int(len(text) * 0.75)


def load_raw_catalog():
    return json.loads(RAW_PATH.read_text(encoding="utf-8"))


def source_by_name(raw_catalog):
    return {source["name"]: source for source in raw_catalog["sources"]}


def promoted_join_candidates(source, limit=8):
    candidates = [
        candidate
        for candidate in source.get("join_candidates", [])
        if candidate.get("promoted")
    ]
    return candidates[:limit]


def source_page_path(source_name):
    return SOURCE_DIR / f"{source_name}.md"


def source_summary(source):
    required_filters = []
    for table in source["tables"]:
        for filter_row in table["filters"]:
            if filter_row["required"]:
                required_filters.append(f"{table['name']}.{filter_row['name']}")

    joins = ", ".join(
        candidate["column"] for candidate in promoted_join_candidates(source, limit=5)
    )
    if not joins:
        joins = "none detected"

    if source["name"] == "ops_incident_demo":
        use_for = "incident root-cause analysis across PRs, deploys, errors, tickets, Slack"
    elif source["name"] == "github":
        use_for = "GitHub repos, PRs, issues, Actions, deployments; many tables require filters"
    else:
        use_for = f"{source['name']} data"

    return {
        "name": source["name"],
        "table_count": source["table_count"],
        "use_for": use_for,
        "source_page": str(source_page_path(source["name"]).as_posix()),
        "join_keys": joins,
        "required_filter_examples": required_filters[:8],
        "required_filter_count": len(required_filters),
    }


def render_index(sources):
    lines = [
        "# Coral Catalog Index",
        "",
        "Injected default. Load one source page only when needed.",
        "",
    ]
    for summary in sources:
        filters = "none" if summary["required_filter_count"] == 0 else f"{summary['required_filter_count']} required filters"
        lines.append(
            f"- `{summary['name']}` ({summary['table_count']} tables): {summary['use_for']}. "
            f"Load `{summary['source_page']}`. Joins: {summary['join_keys']}. Filters: {filters}."
        )
    text = "\n".join(lines).rstrip() + "\n"
    return text


def rank_columns(table, join_columns):
    columns = {column["name"]: column for column in table["columns"]}
    preferred = OPS_TABLE_COLUMNS.get(table["name"], [])
    ranked = []

    for name in preferred:
        if name in columns and name not in ranked:
            ranked.append(name)
    for name in join_columns:
        if name in columns and name not in ranked:
            ranked.append(name)
    for column in table["columns"]:
        name = column["name"]
        if len(ranked) >= 5:
            break
        if (
            name not in ranked
            and (
                name == "id"
                or name.endswith("_id")
                or name.endswith("_at")
                or name in {"author", "status", "title", "summary", "severity"}
            )
        ):
            ranked.append(name)

    if not ranked:
        ranked = [column["name"] for column in table["columns"][:4]]
    return ranked[:5]


def join_columns_by_table(source):
    by_table = {table["name"]: set() for table in source["tables"]}
    for candidate in promoted_join_candidates(source, limit=25):
        for table in candidate["tables"]:
            for column in table.get("columns") or [candidate["column"]]:
                if table["name"] in by_table:
                    by_table[table["name"]].add(column)
    return by_table


def compact_table_line(table, join_columns):
    lookup = {column["name"]: column for column in table["columns"]}
    ranked = rank_columns(table, join_columns)
    columns = ", ".join(f"{name}:{lookup[name]['type']}" for name in ranked if name in lookup)
    filters = [
        f"{filter_row['name']}=<value>"
        for filter_row in table["filters"]
        if filter_row["required"]
    ]
    suffix = f" required: {', '.join(filters)}" if filters else ""
    desc = (table.get("description") or "").strip().rstrip(".")
    if len(desc) > 80:
        desc = desc[:77].rstrip() + "..."
    return f"- `{table['name']}`: {columns}{suffix}. {desc}"


def render_ops_source(source):
    table_by_name = {table["name"]: table for table in source["tables"]}
    order = [
        "github_prs",
        "deployments",
        "incidents",
        "sentry_events",
        "support_tickets",
        "slack_messages",
    ]
    joins = join_columns_by_table(source)
    query = (
        "SELECT p.pr_number,p.author,d.deployment_id,i.incident_id,"
        "COUNT(DISTINCT s.event_id) errors,COUNT(DISTINCT t.ticket_id) tickets "
        "FROM ops_incident_demo.github_prs p "
        "JOIN ops_incident_demo.deployments d ON d.related_pr=p.pr_number "
        "JOIN ops_incident_demo.incidents i ON i.deployment_id=d.deployment_id "
        "JOIN ops_incident_demo.sentry_events s ON s.incident_id=i.incident_id "
        "JOIN ops_incident_demo.support_tickets t ON t.incident_id=i.incident_id "
        "GROUP BY 1,2,3,4 ORDER BY 5 DESC LIMIT 5"
    )
    lines = [
        "# ops_incident_demo",
        "Use: incident root cause across PRs, deploys, errors, tickets, Slack.",
        "Join: `github_prs.pr_number=deployments.related_pr`; `deployments.deployment_id=incidents.deployment_id`; `incidents.incident_id -> sentry_events/support_tickets/slack_messages`.",
        "Tables:",
    ]
    for name in order:
        if name in table_by_name:
            table = table_by_name[name]
            lookup = {column["name"]: column for column in table["columns"]}
            ranked = rank_columns(table, joins[name])[:4]
            columns = ",".join(f"{col}:{lookup[col]['type']}" for col in ranked if col in lookup)
            lines.append(f"- `{name}` {columns}")
    lines.append("Recipe ids: `ops_incident_root_cause`, `ops_incident_impact`, `ops_incident_slack`, `ops_incident_recovery`.")
    return "\n".join(lines).rstrip() + "\n"


def render_large_source(source):
    joins = join_columns_by_table(source)
    table_by_name = {table["name"]: table for table in source["tables"]}
    chosen = []
    for name in HIGH_VALUE_GITHUB_TABLES:
        if name in table_by_name and name not in chosen:
            chosen.append(name)
    if len(chosen) < 12:
        for table in sorted(source["tables"], key=lambda item: len(item["filters"]), reverse=True):
            if table["name"] not in chosen:
                chosen.append(table["name"])
            if len(chosen) >= 12:
                break

    required_count = sum(
        1
        for table in source["tables"]
        for filter_row in table["filters"]
        if filter_row["required"]
    )
    key_join_names = ", ".join(
        candidate["column"] for candidate in promoted_join_candidates(source, limit=6)
    )
    lines = [
        f"# {source['name']}",
        "",
        f"{source['table_count']} tables. Inject this page only for GitHub tasks; most provider tables need required filters.",
        f"Common join keys: {key_join_names}. Required filter count: {required_count}.",
        "",
        "High-value tables:",
    ]
    for name in chosen:
        lines.append(compact_table_line(table_by_name[name], joins.get(name, set())))
    lines.append("")
    lines.append("For an unlisted table, use live `list_columns`/`describe_table` narrowly for that table.")
    return "\n".join(lines).rstrip() + "\n"


def render_generic_source(source):
    joins = join_columns_by_table(source)
    lines = [f"# {source['name']}", "", f"{source['table_count']} tables.", "", "Tables:"]
    for table in source["tables"][:30]:
        lines.append(compact_table_line(table, joins.get(table["name"], set())))
    if len(source["tables"]) > 30:
        lines.append(f"- {len(source['tables']) - 30} more tables omitted; use narrow live discovery.")
    return "\n".join(lines).rstrip() + "\n"


def render_source_page(source):
    if source["name"] == "ops_incident_demo":
        return render_ops_source(source)
    if source["table_count"] > 30:
        return render_large_source(source)
    return render_generic_source(source)


def build_recipes(sources):
    recipes = {}
    names = {source["name"] for source in sources}
    if "ops_incident_demo" in names:
        recipes["ops_incident_root_cause"] = {
            "src": "ops_incident_demo",
            "use": "Find causal PR/deploy/incident with linked errors and tickets.",
            "tables": "github_prs,deployments,incidents,sentry_events,support_tickets",
            "sql": (
                "SELECT p.pr_number,p.title,p.author,d.deployment_id,d.deployed_at,i.incident_id,i.severity,"
                "COUNT(DISTINCT s.event_id) errors,COUNT(DISTINCT t.ticket_id) tickets "
                "FROM ops_incident_demo.github_prs p "
                "JOIN ops_incident_demo.deployments d ON d.related_pr=p.pr_number "
                "JOIN ops_incident_demo.incidents i ON i.deployment_id=d.deployment_id "
                "LEFT JOIN ops_incident_demo.sentry_events s ON s.incident_id=i.incident_id "
                "LEFT JOIN ops_incident_demo.support_tickets t ON t.incident_id=i.incident_id "
                "GROUP BY 1,2,3,4,5,6,7 ORDER BY 8 DESC LIMIT 5"
            ),
        }
        recipes["ops_incident_impact"] = {
            "src": "ops_incident_demo",
            "use": "Break down Sentry and support impact for a known incident_id.",
            "param": "incident_id",
            "tables": "sentry_events,support_tickets",
            "sql": (
                "SELECT 'sentry' kind,error_type detail,COUNT(*) n FROM ops_incident_demo.sentry_events WHERE incident_id='<incident_id>' GROUP BY 1,2 "
                "UNION ALL "
                "SELECT 'tickets' kind,status detail,COUNT(*) n FROM ops_incident_demo.support_tickets WHERE incident_id='<incident_id>' GROUP BY 1,2 "
                "ORDER BY kind,n DESC"
            ),
        }
        recipes["ops_incident_slack"] = {
            "src": "ops_incident_demo",
            "use": "Get Slack timeline evidence for a known incident_id.",
            "param": "incident_id",
            "tables": "slack_messages",
            "sql": (
                "SELECT timestamp,channel,user,message FROM ops_incident_demo.slack_messages "
                "WHERE incident_id='<incident_id>' ORDER BY timestamp LIMIT 15"
            ),
        }
        recipes["ops_incident_recovery"] = {
            "src": "ops_incident_demo",
            "use": "Find rollback and follow-up PRs for a causal PR number.",
            "param": "pr_number",
            "tables": "github_prs,deployments",
            "sql": (
                "SELECT p.pr_number,p.title,p.author,p.reverts_pr,p.fixes_pr,d.deployment_id,d.deployed_at,d.status "
                "FROM ops_incident_demo.github_prs p LEFT JOIN ops_incident_demo.deployments d ON d.deployment_id=p.deployment_id "
                "WHERE p.pr_number=<pr_number> OR p.reverts_pr=<pr_number> OR p.fixes_pr=<pr_number> ORDER BY p.merged_at"
            ),
        }
    return recipes


def write_outputs(raw_catalog):
    OUT_DIR.mkdir(exist_ok=True)
    SOURCE_DIR.mkdir(exist_ok=True)
    summaries = [source_summary(source) for source in raw_catalog["sources"]]
    index_text = render_index(summaries)
    INDEX_MD.write_text(index_text, encoding="utf-8")
    INDEX_JSON.write_text(
        json.dumps({"sources": summaries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    source_metrics = []
    for source in raw_catalog["sources"]:
        page_text = render_source_page(source)
        page_path = source_page_path(source["name"])
        page_path.write_text(page_text, encoding="utf-8")
        source_metrics.append(
            {
                "source": source["name"],
                "path": str(page_path.as_posix()),
                "tokens": estimate_tokens(page_text),
            }
        )

    recipes = build_recipes(raw_catalog["sources"])
    RECIPES_JSON.write_text(
        json.dumps(recipes, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    skill = """# Coral Optimized Catalog Skill

Start with `optimized_catalog/catalog_index.md`. Load only the named source page needed for the task. Use `optimized_catalog/query_recipes.json` when a recipe matches the user's question. Do not inject full raw catalog files unless asked for exhaustive schema coverage.

Fallback: if a needed source/table is absent or a query fails because schema changed, run narrow live Coral discovery for that source/table and rebuild the catalog.
"""
    SKILL_MD.write_text(skill, encoding="utf-8")

    return {
        "index_tokens": estimate_tokens(index_text),
        "source_metrics": source_metrics,
        "recipe_tokens": estimate_tokens(json.dumps(recipes)),
    }


def main():
    raw_catalog = load_raw_catalog()
    metrics = write_outputs(raw_catalog)
    print(f"Wrote {INDEX_MD}")
    print(f"Wrote {INDEX_JSON}")
    print(f"Wrote {RECIPES_JSON}")
    print(f"Wrote {SKILL_MD}")
    print(f"Index tokens ~= {metrics['index_tokens']}")
    print(f"Recipe cache tokens ~= {metrics['recipe_tokens']}")
    for metric in metrics["source_metrics"]:
        print(f"{metric['source']} page tokens ~= {metric['tokens']} ({metric['path']})")


if __name__ == "__main__":
    main()
