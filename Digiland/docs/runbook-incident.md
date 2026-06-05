# Digiland Incident Response Runbook

## Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| P1 - Critical | Service completely down | 15 minutes | Site unreachable, all payments failing |
| P2 - High | Major feature broken | 30 minutes | Login broken, search down |
| P3 - Medium | Partial degradation | 2 hours | Slow responses, intermittent errors |
| P4 - Low | Minor issue | 24 hours | UI glitch, non-critical feature broken |

## Response Process

### 1. Detection

Incidents may be detected through:
- PagerDuty/Slack alerts from Prometheus
- User reports via support
- Manual observation

### 2. Assessment

- Check Grafana dashboards for error rates and latency
- Check CloudWatch logs for exceptions
- Check RDS Performance Insights for database issues
- Determine severity level

### 3. Communication

- Post in #incidents Slack channel
- Include: Severity, Impact, Current Status, Next Steps
- Update every 15 minutes for P1/P2

### 4. Mitigation

For P1/P2 incidents, prioritize restoring service over root cause:
- Consider rollback (see runbook-rollback.md)
- Scale up resources if capacity issue
- Enable maintenance mode if needed
- Failover to secondary if infrastructure issue

### 5. Resolution

- Apply fix or rollback
- Verify service restored
- Monitor for 30 minutes post-resolution

### 6. Post-Incident

- Conduct blameless post-mortem within 48 hours
- Document timeline, root cause, and preventive measures
- Create action items for preventing recurrence
