## Context
Internal SaaS platform for HR management. ~500 concurrent users. Must comply with LGPD (Brazilian data protection law). Budget is limited — single cloud (Azure).

## Architecture (Mermaid)

```mermaid
graph TD
    User -->|HTTPS| LB[Load Balancer]
    LB --> App1[App Server 1]
    LB --> App2[App Server 2]
    App1 --> DB[(SQL Server - Primary)]
    App2 --> DB
    App1 --> Cache[Redis]
    App2 --> Cache
    App1 --> Storage[Azure Blob Storage]
    App2 --> Storage
    DB --> DBR[(SQL Server - Read Replica)]
    App1 -->|Reports| DBR
    App2 -->|Reports| DBR
    App1 --> Email[SendGrid]
    App2 --> Email
```

## Notes
- Auth is username/password only, stored in SQL Server (bcrypt hashed)
- No API rate limiting implemented yet
- All environments (dev/staging/prod) share the same Azure subscription
- Database backups run nightly, retention = 7 days
- No WAF in front of the load balancer
- Logs are stored in Azure Monitor but no alerts configured
