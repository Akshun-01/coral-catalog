# github

362 tables. Inject this page only for GitHub tasks; most provider tables need required filters.
Common join keys: account__gravatar_id, account__id, account__node_id, actor__gravatar_id, actor__id, actor__node_id. Required filter count: 584.

High-value tables:
- `repos_get`: created_at:Utf8, id:Int64, license__node_id:Utf8, license__spdx_id:Utf8, node_id:Utf8 required: owner=<value>, repo=<value>. Get a repository
- `pulls`: assignee__id:Int64, assignee__gravatar_id:Utf8, assignee__node_id:Utf8, assignee__starred_at:Utf8, base__repo__created_at:Utf8 required: owner=<value>, repo=<value>. List pull requests
- `issues`: assignee__id:Int64, assignee__gravatar_id:Utf8, assignee__node_id:Utf8, assignee__starred_at:Utf8, closed_at:Utf8. List issues assigned to the authenticated user
- `repo_issue_events`: actor__node_id:Utf8, assigner__node_id:Utf8, assigner__gravatar_id:Utf8, assignee__gravatar_id:Utf8, actor__id:Int64 required: owner=<value>, repo=<value>. List issue events for a repository
- `timeline`: actor__node_id:Utf8, assignee__gravatar_id:Utf8, actor__id:Int64, actor__gravatar_id:Utf8, assignee__id:Int64 required: issue_number=<value>, owner=<value>, repo=<value>. List timeline events for an issue
- `repo_action_runs`: actor__node_id:Utf8, actor__id:Int64, actor__gravatar_id:Utf8, actor__starred_at:Utf8, check_suite_id:Int64 required: owner=<value>, repo=<value>. List workflow runs for a repository
- `repo_action_workflow_runs`: actor__node_id:Utf8, actor__id:Int64, actor__gravatar_id:Utf8, actor__starred_at:Utf8, check_suite_id:Int64 required: owner=<value>, repo=<value>, workflow_id=<value>. List workflow runs for a workflow
- `repo_pull_comments`: comment_id:Int64, commit_id:Utf8, created_at:Utf8, id:Int64, in_reply_to_id:Int64 required: owner=<value>, repo=<value>. List review comments in a repository
- `repo_pull_review_comments`: commit_id:Utf8, created_at:Utf8, id:Int64, in_reply_to_id:Int64, node_id:Utf8 required: owner=<value>, pull_number=<value>, repo=<value>, review_id=<value>. List comments for a pull request review
- `repo_deployments`: created_at:Utf8, creator__gravatar_id:Utf8, creator__id:Int64, creator__node_id:Utf8, creator__starred_at:Utf8 required: owner=<value>, repo=<value>. List deployments
- `repo_deployment_statuses`: created_at:Utf8, creator__gravatar_id:Utf8, creator__id:Int64, creator__node_id:Utf8, creator__starred_at:Utf8 required: deployment_id=<value>, owner=<value>, repo=<value>. List deployment statuses
- `advisories`: cve_id:Utf8, ghsa_id:Utf8, github_reviewed_at:Utf8, nvd_published_at:Utf8, published_at:Utf8. List global security advisories

For an unlisted table, use live `list_columns`/`describe_table` narrowly for that table.
