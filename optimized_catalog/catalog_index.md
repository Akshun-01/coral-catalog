# Coral Catalog Index

Injected default. Load one source page only when needed.

- `github` (362 tables): GitHub repos, PRs, issues, Actions, deployments; many tables require filters. Load `./sources/github.md`. Joins: account__gravatar_id, account__id, account__node_id, actor__gravatar_id, actor__id. Filters: 584 required filters.
- `ops_incident_demo` (6 tables): incident root-cause analysis across PRs, deploys, errors, tickets, Slack. Load `./sources/ops_incident_demo.md`. Joins: deployment_id, incident_id, related_pr. Filters: none.
