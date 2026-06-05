# Operations Runbook

## Provider Outage Procedures

When an external service provider experiences an outage, the ESL's automated resilience mechanisms (circuit breakers, fallback chains, retry with backoff) handle the immediate impact. However, provider outages require operational oversight to ensure that the automated response is effective and that any data inconsistencies are resolved. This section describes the step-by-step procedure for responding to a provider outage.

**Step 1: Detection and Acknowledgement** — Provider outages are detected through automated monitoring: the `esl_circuit_breaker_state` Prometheus metric transitions to OPEN, the `esl_provider_health_status` metric drops below the healthy threshold, or the `esl_error_rate` metric exceeds the configured alert threshold. PagerDuty sends an alert to the on-call engineer, who must acknowledge it within 5 minutes. The alert includes the service type, provider name, circuit breaker state, and recent error summary.

**Step 2: Impact Assessment** — The on-call engineer assesses the blast radius by checking: (a) which service types are affected, (b) whether fallback providers are healthy and serving traffic, (c) whether the DLQ is accumulating entries, and (d) whether any user-facing features are degraded. The `esl_health_check` management command provides a quick overview of all provider health statuses. The engineer also checks the provider's status page (listed in the Emergency Contacts section) to determine whether the outage is known and estimated recovery time.

**Step 3: Fallback Verification** — If the fallback chain has activated, the engineer verifies that the fallback provider is healthy and performing within acceptable latency bounds. The `esl_fallback_total` and `esl_fallback_duration_seconds` metrics on Grafana show the current fallback rate and latency impact. If the fallback provider is also degraded, the engineer should consider enabling the next provider in the chain or activating the feature toggle to disable the service type entirely.

**Step 4: Communication** — The engineer posts an update to the `#incidents` Slack channel with: (a) the affected service type and provider, (b) the current fallback status, (c) the estimated user impact, and (d) the next check-in time. If the outage affects payment processing or escrow operations, the product team and customer support team must be notified immediately.

**Step 5: Monitoring** — The engineer monitors the outage at regular intervals (every 15 minutes for critical services, every 30 minutes for non-critical services) until the provider recovers or the outage is escalated. Key metrics to watch: `esl_circuit_breaker_state`, `esl_error_rate`, `esl_fallback_total`, `esl_dlq_entries_pending`, and the provider's status page.

**Step 6: Resolution** — When the provider recovers, the circuit breaker transitions through HALF_OPEN to CLOSED automatically. The engineer verifies that normal traffic has resumed, checks the DLQ for entries that require replay, and runs the data reconciliation process if the outage lasted more than 15 minutes. A resolution update is posted to the `#incidents` channel.

## Failover Procedures

Failover is the process of intentionally switching from one provider to another, either in response to an outage or as part of planned maintenance. The ESL supports both automatic failover (through fallback chains) and manual failover (through registry operations).

**Automatic Failover** — Automatic failover occurs when the circuit breaker opens for the primary provider and the registry walks the fallback chain to find a healthy alternative. This is the default behaviour and requires no manual intervention. The engineer should verify that the failover has occurred correctly by checking the `esl_fallback_total` metric and confirming that the fallback provider is handling traffic.

**Manual Failover** — Manual failover is required when: (a) the fallback chain is not configured or is insufficient, (b) the primary provider needs to be taken offline for planned maintenance, or (c) the automatic failover did not activate correctly. Manual failover is performed using the `esl_failover` management command:

```
python manage.py esl_failover --service-type=payment --from=paystack --to=stripe
```

This command: (1) sets the circuit breaker to OPEN for the `from` provider, (2) sets the `to` provider as the default for the service type, and (3) logs the failover event for audit purposes. The command supports a `--dry-run` flag to preview the failover without executing it.

**Planned Maintenance Failover** — For planned provider maintenance, the engineer should: (1) announce the maintenance window in the `#platform-ops` channel at least 24 hours in advance, (2) verify that the fallback provider is healthy and has sufficient capacity, (3) execute the failover 30 minutes before the maintenance window begins, (4) monitor the fallback provider during the maintenance, and (5) fail back to the primary provider after maintenance is complete, using the `esl_failback` management command.

**Failback** — After a failover, the primary provider should be restored when it is healthy again. Failback is performed using the `esl_failback` management command, which: (1) checks the primary provider's health, (2) gradually shifts traffic back to the primary using a canary approach (10% → 50% → 100%), and (3) logs the failback event. The gradual shift prevents a sudden load spike on the recovering provider.

## Monitoring Alerts

The ESL's monitoring infrastructure produces alerts through Prometheus alerting rules and PagerDuty integration. The following alerts are configured:

| Alert Name | Condition | Severity | Response |
|---|---|---|---|
| `ESLCircuitBreakerOpen` | Circuit breaker OPEN for > 2 minutes | Warning | Check provider status, verify fallback |
| `ESLCircuitBreakerOpenExtended` | Circuit breaker OPEN for > 10 minutes | Critical | Initiate provider outage procedure |
| `ESLHighErrorRate` | Error rate > 5% for 5 minutes | Warning | Investigate provider health |
| `ESLCriticalErrorRate` | Error rate > 20% for 2 minutes | Critical | Initiate provider outage procedure |
| `ESLHighLatency` | P99 latency > SLA target for 5 minutes | Warning | Check provider performance |
| `ESLDeadLetterQueueGrowing` | DLQ entries > 50 or growing at > 5/min | Warning | Review DLQ, check provider status |
| `ESLDeadLetterQueueCritical` | DLQ entries > 500 or growing at > 50/min | Critical | Initiate provider outage procedure, begin DLQ triage |
| `ESLFallbackRateHigh` | Fallback rate > 10% of traffic | Warning | Primary provider may be degraded |
| `ESLProviderUnhealthy` | Health check returns "unhealthy" for > 3 consecutive checks | Warning | Investigate provider connectivity |
| `ESLRateLimitExceeded` | Rate limit errors > 10 in 5 minutes | Info | Review rate limit configuration |

Alerts are routed to PagerDuty with the following escalation policy: Level 1 (on-call engineer) acknowledges within 5 minutes. If unacknowledged after 10 minutes, the alert escalates to Level 2 (engineering lead). If unacknowledged after 20 minutes, the alert escalates to Level 3 (VP Engineering).

## Escalation Paths

When an ESL-related incident cannot be resolved by the on-call engineer, it should be escalated through the following paths:

**Provider-Specific Escalation** — If the incident is caused by a specific provider's outage or degradation:
1. Check the provider's status page for known incidents.
2. If the provider has a support ticket open, reference it in the incident channel.
3. Contact the provider's support team using the emergency contacts below.
4. If the provider is unresponsive for > 30 minutes, escalate internally to the engineering lead.

**Platform Escalation** — If the incident is caused by a bug or misconfiguration in the ESL itself:
1. Collect diagnostic information: error logs, circuit breaker state, DLQ entries, recent configuration changes.
2. Post the information in the `#incidents` channel with the tag `esl-critical`.
3. The engineering lead reviews and assigns a senior engineer for investigation.
4. If the issue requires a code fix, follow the hotfix deployment process.

**Business Escalation** — If the incident has a significant business impact (e.g. payments cannot be processed, escrow operations are blocked):
1. Notify the product manager and customer support lead immediately.
2. If the outage affects > 100 active transactions, the VP Engineering and COO must be notified.
3. Customer support should proactively communicate with affected users using the approved messaging templates.

**Security Escalation** — If the incident involves suspected credential compromise (e.g. authentication errors that suggest a revoked key, unexpected provider responses):
1. Immediately rotate the affected credentials using the provider's dashboard or CLI.
2. Update the credentials in Django settings and redeploy.
3. Notify the security team via the `#security` channel.
4. Conduct a post-incident security review within 24 hours.

## Emergency Contacts

| Provider | Support Channel | Phone | Status Page |
|---|---|---|---|
| Paystack | support@paystack.com | +234 1 631 7927 | https://status.paystack.com |
| Stripe | https://support.stripe.com | +1 888 527 4683 | https://status.stripe.com |
| M-Pesa (Safaricom) | enterprise.support@safaricom.co.ke | +254 722 002 525 | N/A |
| KCB Bank | digitalbanking@kcbgroup.com | +254 711 087 087 | N/A |
| Salesforce | https://help.salesforce.com | +1 800 667 6389 | https://trust.salesforce.com |
| HubSpot | https://help.hubspot.com | +1 888 482 7768 | https://status.hubspot.com |
| Zoho | https://support.zoho.com | +1 877 834 4428 | https://status.zoho.com |
| SAP | https://support.sap.com | +1 800 672 7638 | https://status.sap.com |
| Oracle ERP | https://support.oracle.com | +1 800 633 0738 | https://ocistatus.oraclecloud.com |
| QuickBooks | https://help.quickbooks.intuit.com | +1 800 488 7330 | https://status.quickbooks.intuit.com |
| Xero | https://central.xero.com/s/contact-support | +64 4 815 8282 | https://status.xero.com |
| SendGrid | https://support.sendgrid.com | N/A | https://status.sendgrid.com |
| Twilio | https://support.twilio.com | +1 888 527 4683 | https://status.twilio.com |
| Africa's Talking | support@africastalking.com | +254 711 060 060 | N/A |
| AWS (S3) | https://aws.amazon.com/support | +1 800 422 5255 | https://health.aws.amazon.com |
| OpenAI | https://help.openai.com | N/A | https://status.openai.com |
| Anthropic | https://support.anthropic.com | N/A | N/A |

For internal Digiland support: on-call engineering rotation is accessible via PagerDuty at `esl-oncall@digiland.pagerduty.com`. The engineering lead is available at `esl-lead@digiland.internal` for L2 escalation. The VP Engineering is available for L3 escalation at `vp-eng@digiland.internal`.
