import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import annotate_catalog
import build_catalog
import optimize_catalog
import render_catalog


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = Path.home() / ".coral" / "catalog"
STATUS_FILE = "catalog_status.json"


def estimate_tokens(text):
    return int(len(text) * 0.75)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copy_file(source, destination_dir):
    destination = destination_dir / source.name
    shutil.copy2(source, destination)
    return destination


def copy_tree(source, destination_dir):
    destination = destination_dir / source.name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination


def current_source_state():
    rows = build_catalog.run_coral_json(
        "SELECT schema_name, table_name FROM coral.tables ORDER BY schema_name, table_name"
    )
    sources = {}
    for row in rows:
        sources.setdefault(row["schema_name"], []).append(row["table_name"])
    return {
        "source_count": len(sources),
        "table_count": sum(len(tables) for tables in sources.values()),
        "sources": {
            name: {
                "table_count": len(tables),
                "tables": tables,
            }
            for name, tables in sorted(sources.items())
        },
    }


def build(output_dir, use_claude):
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_catalog = build_catalog.build_catalog()
    write_json(build_catalog.OUTPUT_PATH, raw_catalog)

    annotated = annotate_catalog.annotate_catalog(use_claude=use_claude)
    write_json(annotate_catalog.OUTPUT_PATH, annotated)

    markdown = render_catalog.render_markdown(annotated)
    clean = render_catalog.clean_json(annotated)
    skill = render_catalog.render_skill()
    render_catalog.CATALOG_MD_PATH.write_text(markdown, encoding="utf-8")
    write_json(render_catalog.CATALOG_JSON_PATH, clean)
    render_catalog.CATALOG_SKILL_PATH.write_text(skill, encoding="utf-8")

    optimize_metrics = optimize_catalog.write_outputs(raw_catalog)

    copied = [
        copy_file(build_catalog.OUTPUT_PATH, output_dir),
        copy_file(annotate_catalog.OUTPUT_PATH, output_dir),
        copy_file(render_catalog.CATALOG_MD_PATH, output_dir),
        copy_file(render_catalog.CATALOG_JSON_PATH, output_dir),
        copy_file(render_catalog.CATALOG_SKILL_PATH, output_dir),
    ]
    optimized_output = copy_tree(optimize_catalog.OUT_DIR, output_dir)

    status = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "source_count": len(raw_catalog["sources"]),
        "table_count": sum(source["table_count"] for source in raw_catalog["sources"]),
        "sources": {
            source["name"]: {
                "table_count": source["table_count"],
                "tables": [table["name"] for table in source["tables"]],
            }
            for source in raw_catalog["sources"]
        },
        "catalog_md_tokens": estimate_tokens(markdown),
        "optimized_index_tokens": optimize_metrics["index_tokens"],
        "optimized_recipe_tokens": optimize_metrics["recipe_tokens"],
        "optimized_sources": optimize_metrics["source_metrics"],
        "files": [str(path) for path in copied] + [str(optimized_output)],
    }
    write_json(output_dir / STATUS_FILE, status)

    print("Catalog built")
    print(f"  Sources:  {status['source_count']}")
    print(f"  Tables:   {status['table_count']}")
    print(f"  Tokens:   {status['catalog_md_tokens']} catalog.md")
    print(f"  Output:   {output_dir / 'catalog.md'}")
    print(f"  Optimized index: {output_dir / 'optimized_catalog' / 'catalog_index.md'}")
    print("")
    print("Rebuild when sources change: coral catalog build")


def status(output_dir):
    status_path = output_dir / STATUS_FILE
    if not status_path.exists():
        print(f"No catalog status found at {status_path}")
        return 1

    saved = json.loads(status_path.read_text(encoding="utf-8"))
    current = current_source_state()

    saved_sources = set(saved["sources"])
    current_sources = set(current["sources"])
    added = sorted(current_sources - saved_sources)
    removed = sorted(saved_sources - current_sources)
    changed = []
    for source in sorted(saved_sources & current_sources):
        saved_tables = set(saved["sources"][source]["tables"])
        current_tables = set(current["sources"][source]["tables"])
        if saved_tables != current_tables:
            changed.append(source)

    print(f"Last built: {saved['built_at']}")
    print(f"Output:     {output_dir}")
    print(f"Sources:    {saved['source_count']}")
    print(f"Tables:     {saved['table_count']}")
    print(f"Current:    {current['source_count']} sources, {current['table_count']} tables")

    if added or removed or changed:
        print("Drift:      yes")
        if added:
            print(f"  Added sources: {', '.join(added)}")
        if removed:
            print(f"  Removed sources: {', '.join(removed)}")
        if changed:
            print(f"  Changed table sets: {', '.join(changed)}")
        return 2

    print("Drift:      no")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(prog="coral_catalog")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build Coral catalog artifacts")
    build_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    build_parser.add_argument(
        "--no-claude",
        action="store_true",
        help="Use deterministic local annotations instead of the Claude API",
    )

    status_parser = subparsers.add_parser("status", help="Show catalog build status")
    status_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)

    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "build":
        build(args.output_dir.expanduser(), use_claude=not args.no_claude)
        return 0
    if args.command == "status":
        return status(args.output_dir.expanduser())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
