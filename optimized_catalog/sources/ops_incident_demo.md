# ops_incident_demo
Use: incident root cause across PRs, deploys, errors, tickets, Slack.
Join: `github_prs.pr_number=deployments.related_pr`; `deployments.deployment_id=incidents.deployment_id`; `incidents.incident_id -> sentry_events/support_tickets/slack_messages`.
Tables:
- `github_prs` pr_number:Int64,author:Utf8,deployment_id:Utf8,reverts_pr:Int64
- `deployments` deployment_id:Utf8,related_pr:Int64,deployed_at:Timestamp,status:Utf8
- `incidents` incident_id:Utf8,deployment_id:Utf8,related_pr:Int64,severity:Utf8
- `sentry_events` event_id:Utf8,incident_id:Utf8,error_type:Utf8,tenant:Utf8
- `support_tickets` ticket_id:Utf8,incident_id:Utf8,plan:Utf8,severity:Utf8
- `slack_messages` timestamp:Timestamp,incident_id:Utf8,user:Utf8,message:Utf8
Recipe ids: `ops_incident_root_cause`, `ops_incident_impact`, `ops_incident_slack`, `ops_incident_recovery`.
