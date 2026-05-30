# Coral Catalog Skill

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
