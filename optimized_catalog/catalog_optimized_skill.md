# Coral Optimized Catalog Skill

Start with `optimized_catalog/catalog_index.md`. Load only the named source page needed for the task. Use `optimized_catalog/query_recipes.json` when a recipe matches the user's question. Do not inject full raw catalog files unless asked for exhaustive schema coverage.

Fallback: if a needed source/table is absent or a query fails because schema changed, run narrow live Coral discovery for that source/table and rebuild the catalog.
