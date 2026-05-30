# Coral Schema Catalog
Generated: 2026-05-30T07:43:53.826693+00:00
Sources: 2  Tables: 368  Estimated tokens: 8093

---
## github  (http)

github exposes 362 API-backed tables. Use required filters before querying provider tables, then join repeated identifier columns where available.

### Joins
account__gravatar_id links app_installations, installation, installation_requests, org_installations, user_installations; account__id links app_installations, installation, installation_requests, marketplace_purchases, org_installations, stubbed, user_installations; account__node_id links app_installations, installation, installation_requests, marketplace_purchases, org_installations, stubbed, user_installations; actor__gravatar_id links activity, attempts, events, issues_list_events, received_events, repo_action_runs, repo_action_workflow_runs, repo_issue_events, timeline, user_event_orgs, user_event_public, user_received_event_public; actor__id links activity, attempts, events, history, issues_list_events, received_events, repo_action_runs, repo_action_workflow_runs, repo_issue_events, timeline, user_event_orgs, user_event_public, user_received_event_public.

### Tables

**repos_get** - Get a repository.
Cols: id (Int64)
Required filters: owner = <value>, repo = <value>

**repo_issue_events** - List issue events for a repository.
Cols: actor__gravatar_id (Utf8)
Required filters: owner = <value>, repo = <value>

**pulls** - List pull requests.
Cols: assignee__gravatar_id (Utf8)
Required filters: owner = <value>, repo = <value>

**issues** - List issues assigned to the authenticated user.
Cols: assignee__gravatar_id (Utf8)

**blocked_by** - List dependencies an issue is blocked by.
Cols: assignee__gravatar_id (Utf8)
Required filters: issue_number = <value>, owner = <value>, repo = <value>

**blocking** - List dependencies an issue is blocking.
Cols: assignee__gravatar_id (Utf8)
Required filters: issue_number = <value>, owner = <value>, repo = <value>

**parent** - Get parent issue.
Cols: assignee__gravatar_id (Utf8)
Required filters: issue_number = <value>, owner = <value>, repo = <value>

**sub_issues** - List sub-issues.
Cols: assignee__gravatar_id (Utf8)
Required filters: issue_number = <value>, owner = <value>, repo = <value>

**user_issues** - List user account issues assigned to the authenticated.
Cols: assignee__gravatar_id (Utf8)

**timeline** - List timeline events for an issue.
Cols: actor__gravatar_id (Utf8)
Required filters: issue_number = <value>, owner = <value>, repo = <value>

**repo_action_runs** - List workflow runs for a repository.
Cols: actor__gravatar_id (Utf8)
Required filters: owner = <value>, repo = <value>

**attempts** - Get a workflow run attempt.
Cols: actor__gravatar_id (Utf8)
Required filters: attempt_number = <value>, owner = <value>, repo = <value>, run_id = <value>

**repo_action_workflow_runs** - List workflow runs for a workflow.
Cols: actor__gravatar_id (Utf8)
Required filters: owner = <value>, repo = <value>, workflow_id = <value>

**events** - List public events.
Cols: actor__gravatar_id (Utf8)

**received_events** - List events received by the authenticated user.
Cols: actor__gravatar_id (Utf8)
Required filters: username = <value>

Additional tables summarized by name: accepted_assignments, access, accounts, activity, activity_list_repos_starred_by_user, activity_list_repos_watched_by_user, advisories, alerts, analyses, annotations, app, app_hook_config, app_hook_deliveries, app_installations, approvals, apps, artifact_and_log_retention, assignees, assignments, attestations, authors, autofix, autolinks, automated_security_fixes, billing, blobs, branches_where_head, budgets, builds, caches, campaigns, check_runs, classroom_assignments, classrooms, clones, code_frequency, code_security_configuration, codes_of_conduct, codespaces, collaborators, comments, commit_activity, commits, config, configurations, conflicts, content_exclusion, contents, contexts, copilot, custom, databases, default_setup, defaults, deliveries, deployment_branch_policies, deployment_protection_rules, deployment_records, devcontainers, downloads, emails, emojis, enforce_admins, enterprise_1_day, enterprise_code_security_configuration_repositories, enterprise_copilot_metric_report_enterprise_28_day_latest, enterprise_team_memberships, enterprise_teams, environments, errors, exports, failed_invitations, feeds, fields, files, fork_pr_contributor_approval, fork_pr_workflows_private_repos, gist, gist_comments, gist_commits, gist_forks, gist_public, gist_starred, gists, github_owned, grades, health, history, hovercard, import, installation, installation_repositories, installation_requests, instances, interaction_limits, invitations, issue_field_values, issue_fields, issue_types, issues_list_comments, issues_list_events, items, jobs, labels, languages, large_files, latest, license, licenses, limits, locations, machine_sizes, marketplace_listing_accounts, marketplace_listing_plans, marketplace_listing_stubbed_plans, marketplace_purchases, matching_refs, members, memberships, meta, meta_get_all_versions, metrics, milestones, network_configurations, network_settings, new, notification_thread_subscription, notifications, org_action_cache_usage, org_action_hosted_runner_image_custom_versions, org_action_hosted_runners, org_action_oidc_customization_sub, org_action_permission_repositories, org_action_permission_self_hosted_runner_repositories, org_action_permissions, org_action_runner_group_hosted_runners, org_action_runner_group_runners, org_action_secret_public_key, org_action_secrets, org_action_variables, org_attestation_repositories, org_attestations, org_blocks, org_code_scanning_alerts, org_codespace_secrets, org_copilot_coding_agent_permission_repositories, org_copilot_coding_agent_permissions, org_copilot_metric_report_organization_28_day_latest, org_dependabot_secret_public_key, org_dependabot_secrets, org_hooks, org_insight_summary_stat_users, org_insight_summary_stats, org_insight_time_stat_users, org_insight_time_stats, org_insights_summary_stat, org_insights_time_stat, org_installations, org_memberships, org_migrations, org_organization_role_teams, org_organization_role_users, org_private_registry_public_key, org_property_values, org_repos, org_secret_scanning_alerts, org_setting_immutable_release_repositories, org_setting_immutable_releases, organization_1_day, organization_roles, organization_secrets, organization_setting_billing_usage, organization_variables, organizations, orgs, orgs_list_for_user, outside_collaborators, packages, packages_list_packages_for_authenticated_user, pages, participation, partner, paths, pattern_configurations, pending_deployments, permission, permissions_check, personal_access_token_requests, personal_access_tokens, platforms, private_registries, private_vulnerability_reporting, profile, projects_v2, protection, public_emails, public_key, public_members, pulls_list_review_comments, punch_card, rate_limit, reactions, readme, ref, referrers, releases, repo, repo_action_artifacts, repo_action_cache_usage, repo_action_jobs, repo_action_oidc_customization_sub, repo_action_permissions, repo_action_run_artifacts, repo_action_run_timing, repo_action_secrets, repo_action_variables, repo_action_workflow_timing, repo_branch_protection_restriction_apps, repo_branch_protection_restriction_teams, repo_branch_protection_restriction_users, repo_branches, repo_check_runs, repo_check_suites, repo_code_scanning_alerts, repo_code_scanning_codeql_variant_analyse_repos, repo_codespace_machines, repo_codespace_secrets, repo_commit_check_suites, repo_commit_statuses, repo_compare, repo_contributors, repo_dependabot_alerts, repo_dependabot_secrets, repo_dependency_graph_compare, repo_deployment_statuses, repo_deployments, repo_environment_deployment_protection_rule_apps, repo_environment_secret_public_key, repo_environment_secrets, repo_environment_variables, repo_forks, repo_git_commits, repo_git_tags, repo_hooks, repo_immutable_releases, repo_invitations, repo_issue_comments, repo_keys, repo_labels, repo_page_build_latest, repo_page_deployments, repo_property_values, repo_pull_comments, repo_pull_review_comments, repo_release_assets, repo_release_latest, repo_release_tags, repo_rule_branches, repo_secret_scanning_alerts, repo_stat_contributors, repo_subscription, repo_tags, repo_topics, repos, repos_list_release_assets, repositories, repository_access, repository_invitations, requested_reviewers, required_pull_request_reviews, required_signatures, required_status_checks, restrictions, retention_limit, reviews, route_stats, rows, rule_suites, rulesets, runner_groups, runners, sarifs, sbom, scan_history, schema, seats, security_advisories, security_managers, selected_actions, self_hosted_runners, stargazers, status, storage_limit, storage_records, stubbed, subject_stats, subscribers, summary, team, teams, templates, threads, trees, usage, usage_by_repository, user, user_blocks, user_codespace_machines, user_codespace_secret_public_key, user_codespace_secrets, user_codespaces, user_docker_conflicts, user_event_orgs, user_event_public, user_followers, user_following, user_gpg_keys, user_installation_repositories, user_installations, user_interaction_limits, user_keys, user_membership_orgs, user_migrations, user_orgs, user_packages, user_received_event_public, user_repos, user_setting_billing_usage, user_social_accounts, user_ssh_signing_keys, user_starred, user_stats, user_subscriptions, user_teams, users, users_1_day, users_list_followers_for_user, users_list_following_for_user, users_list_gpg_keys_for_user, users_list_public_keys_for_user, users_list_social_accounts_for_user, users_list_ssh_signing_keys_for_user, variant_analyses, versions, views, workflow, workflows

### Query

```sql
SELECT * FROM github.app_installations a JOIN github.installation b ON b.account__gravatar_id = a.account__gravatar_id LIMIT 20
```

---

## ops_incident_demo  (jsonl)
Incident demo: PRs, deploys, errors, tickets.
### Joins
Join PR -> deployment by `related_pr`, deployment -> incident by `deployment_id`, then `incident_id` to errors/tickets/Slack.
### Tables
**deployments** - Deployments.
Cols: deployment_id (Utf8)
**github_prs** - PRs.
Cols: pr_number (Int64)
**incidents** - Incidents.
Cols: incident_id (Utf8)
**sentry_events** - Errors.
Cols: event_id (Utf8)
**slack_messages** - Slack.
Cols: related_pr (Int64)
**support_tickets** - Tickets.
Cols: ticket_id (Utf8)
### Query
```sql
SELECT p.pr_number,count(DISTINCT s.event_id) errors,count(DISTINCT t.ticket_id) tickets FROM ops_incident_demo.github_prs p JOIN ops_incident_demo.deployments d ON d.related_pr=p.pr_number JOIN ops_incident_demo.incidents i ON i.deployment_id=d.deployment_id JOIN ops_incident_demo.sentry_events s ON s.incident_id=i.incident_id JOIN ops_incident_demo.support_tickets t ON t.incident_id=i.incident_id GROUP BY 1 ORDER BY 2 DESC LIMIT 5
```
