# Disaster Recovery

## RPO/RTO Targets

The ESL's disaster recovery strategy is designed around clearly defined Recovery Point Objective (RPO) and Recovery Time Objective (RTO) targets for each service category. RPO defines the maximum acceptable data loss in the event of a disaster, measured as the time between the last successful data sync and the disaster event. RTO defines the maximum acceptable time to restore service after a disaster.

| Service Category | RPO Target | RTO Target | Rationale |
|---|---|---|---|
| Payment | 0 (zero data loss) | 5 minutes | Financial transactions require strict consistency; any data loss could result in incorrect balances or lost payments |
| CRM | 15 minutes | 30 minutes | CRM data is synchronised asynchronously; a 15-minute gap is acceptable as changes can be reconciled |
| ERP | 15 minutes | 30 minutes | ERP data is batch-synced; reconciliation processes can recover from gaps |
| Accounting | 0 (zero data loss) | 15 minutes | Accounting records must be complete and accurate for compliance; every entry must be recoverable |
| Email/SMS | 1 hour | 15 minutes | Messages can be re-sent from the queue; delivery status may be lost but can be re-queried |
| Storage | 0 (zero data loss) | 10 minutes | Documents (title deeds, identity documents) are irreplaceable; multi-region replication ensures zero loss |
| AI | N/A | 5 minutes | AI is stateless; no persistent data to recover |
| Search | 1 hour | 30 minutes | Search indices can be rebuilt from the primary database |

The zero-RPO targets for payment, accounting, and storage are achieved through synchronous write-ahead logging and multi-region replication. Every payment operation is written to the database before the provider is called, ensuring that the operation can be recovered even if the provider call is lost. Accounting entries are written to an immutable audit log that is replicated to a secondary data centre in real time. Storage objects are uploaded to the primary bucket and asynchronously replicated to a secondary bucket in a different region.

The RTO targets assume that the disaster affects only the ESL's infrastructure (application servers, database, cache) and not the external providers themselves. If a provider also experiences a disaster, the RTO is extended by the provider's own recovery time, and the ESL falls back to the next provider in the chain.

## Backup Procedures

The ESL's backup strategy covers four categories of data: configuration, operational state, persistent queues, and audit logs.

**Configuration Backups** — All ESL configuration is stored in Django settings, which are version-controlled in Git. Configuration backups are therefore implicit — any configuration change is tracked in the Git history and can be rolled back. Provider credentials (API keys, OAuth2 tokens) are stored in environment variables or a secrets manager (AWS Secrets Manager, HashiCorp Vault), which have their own backup and recovery mechanisms. Configuration backups are tested quarterly by deploying a fresh environment from the Git repository and verifying that all providers can connect.

**Operational State Backups** — The ESL's operational state includes circuit breaker states, rate limiter buckets, and cache contents. This state is ephemeral and can be reconstructed from the database after a restart. Circuit breaker states reset to CLOSED on restart, which is safe because the circuit breaker will re-evaluate the provider's health on the first call. Rate limiter buckets start empty, which may allow a brief burst of traffic after restart but is self-correcting. Cache contents are rebuilt lazily as requests are served.

**Persistent Queue Backups** — The retry queue and dead-letter queue (DLQ) are backed by the Django database, which is backed up using PostgreSQL's continuous WAL archiving. WAL archives are shipped to a secondary data centre every 60 seconds, providing an RPO of approximately 1 minute for queue data. Full database backups are taken daily and retained for 30 days. Point-in-time recovery is supported through WAL replay, allowing the database to be restored to any point within the retention period.

**Audit Log Backups** — The ESL's audit log records every external service call, including the request payload, response payload, latency, error details, and cost. Audit logs are written to the database and also streamed to a dedicated log aggregation service (Elasticsearch or CloudWatch Logs). Log aggregation provides redundancy and enables fast searching during incident investigation. Audit logs are retained for 7 years for compliance purposes (aligned with financial record-keeping requirements).

**Backup Verification** — Backup integrity is verified weekly through an automated restore test. The test restores the most recent backup to a staging environment and runs the ESL's integration test suite against it. Any restore failures or data inconsistencies are escalated to the database administration team. Backup verification results are recorded in the compliance audit trail.

## Recovery Steps

The ESL's recovery procedure is a structured sequence of steps that restores service after a disaster. The procedure is designed to be executed by an on-call engineer without requiring specialist knowledge of the ESL's internals.

**Step 1: Assess the Disaster** — Determine the scope of the disaster: is it a single-provider outage, a full application server failure, a database failure, or a data centre outage? The assessment determines which recovery steps are needed. Check: (a) the application server status, (b) the database status, (c) the cache status, and (d) the external provider health dashboard.

**Step 2: Activate the Incident Response Team** — If the disaster affects multiple service categories or the RTO target is at risk, activate the incident response team: on-call engineer (L1), engineering lead (L2), VP Engineering (L3). Notify the team via PagerDuty and the `#incidents` Slack channel.

**Step 3: Restore Infrastructure** — If application servers are down, deploy fresh instances from the latest CI/CD artefact. If the database is down, initiate point-in-time recovery from the most recent backup. If the cache is down, allow it to rebuild lazily (no action needed). Infrastructure restoration should be automated through IaC (Terraform, CloudFormation) and takes approximately 5-10 minutes.

**Step 4: Verify Provider Connectivity** — Once infrastructure is restored, run the `esl_health_check` management command to verify that all providers are reachable. The command checks each registered provider and reports their health status. If any providers are unreachable, verify that the provider credentials are correct and that the provider's status page shows no ongoing outage.

**Step 5: Reconcile In-Flight Operations** — Identify any operations that were in progress when the disaster occurred. These may include: (a) payment transactions that were initiated but not confirmed, (b) CRM sync operations that were queued but not processed, (c) email/SMS messages that were composed but not sent. For payment transactions, run the `esl_reconcile_payments` management command, which queries each payment provider for the status of all transactions that were in a "pending" state. For CRM/ERP sync operations, run the `esl_reconcile_sync` management command, which compares the Digiland database with the external provider and flags discrepancies.

**Step 6: Replay the DLQ** — Run the `esl_replay_dlq` management command to process any operations that were dead-lettered during the disaster. Review each DLQ entry before replaying to ensure that the operation is still valid (e.g. a payment refund that was dead-lettered may no longer be appropriate if the original payment was already refunded through a manual process). Replay operations in chronological order to maintain consistency.

**Step 7: Verify Data Integrity** — Run the `esl_verify_integrity` management command, which performs a comprehensive check of the ESL's data integrity: (a) all payment transactions in the database have a corresponding provider reference, (b) all CRM/ERP sync operations have been completed, (c) the accounting ledger balances, (d) no orphaned records exist in the DLQ. Any integrity violations are reported and flagged for manual review.

**Step 8: Restore Normal Operations** — Once all recovery steps are complete, verify that the platform is operating normally by running the end-to-end test suite in production (behind a feature flag). Monitor the `esl_error_rate` and `esl_latency_p99` metrics for 30 minutes to ensure that the recovery is stable. Post a resolution update in the `#incidents` channel.

**Step 9: Post-Recovery Review** — Within 48 hours of the disaster, conduct a post-recovery review to: (a) document the root cause, (b) evaluate the effectiveness of the recovery procedure, (c) identify any gaps in the backup or recovery process, and (d) create action items for improvement. The review is documented in the incident management system and tracked to completion.

## Testing Schedule

The ESL's disaster recovery plan is tested on a regular schedule to ensure that it remains effective as the system evolves. Testing is categorised into three levels:

**Level 1: Automated Weekly Tests** — These tests run automatically as part of the CI/CD pipeline and verify basic recovery capabilities:
- Backup integrity verification (restore to staging, run integration tests)
- Provider health check (all registered providers reachable)
- DLQ replay (replay a sample of DLQ entries and verify success)
- Configuration deployment (deploy to a fresh environment and verify connectivity)

Automated tests run every Sunday at 02:00 UTC and take approximately 30 minutes. Results are posted to the `#platform-reliability` Slack channel and tracked in the reliability dashboard.

**Level 2: Monthly DR Drills** — These drills simulate a realistic disaster scenario and require manual execution by the on-call engineer:
- Simulated provider outage (disable a provider's DNS, verify fallback activation)
- Simulated database failure (promote a read replica, verify data consistency)
- Simulated application server failure (terminate an instance, verify auto-scaling)
- Simulated credential compromise (rotate credentials, verify update propagation)

Monthly drills are scheduled on the first Saturday of each month at 06:00 UTC and take approximately 2 hours. The on-call engineer follows the recovery steps documented in this runbook and records the actual RTO achieved. Any deviations from the expected procedure are documented as action items.

**Level 3: Quarterly Full DR Exercises** — These exercises test the complete disaster recovery plan end-to-end, including escalation, communication, and manual recovery steps:
- Full data centre failover (shift traffic to the secondary region)
- Complete infrastructure rebuild from IaC (destroy and recreate the production environment)
- Multi-provider outage simulation (disable two providers simultaneously)
- Data corruption recovery (restore from backup and verify data integrity)

Quarterly exercises are scheduled in advance with the engineering team and take a full business day. The exercise is led by the engineering lead, observed by the VP Engineering, and documented in a formal DR exercise report. The report includes: the scenario tested, the steps executed, the actual RPO and RTO achieved, any issues encountered, and recommendations for improvement.

**Continuous Improvement** — After each test level, findings are triaged and prioritised. Critical findings (RTO exceedance, data loss, inability to recover) are addressed within one sprint. High-priority findings (procedure gaps, monitoring blind spots) are addressed within two sprints. Low-priority findings (documentation improvements, alert tuning) are added to the backlog. All improvements are verified in the next scheduled test.
