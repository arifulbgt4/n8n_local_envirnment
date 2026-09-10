# V4.2 modular workflows (recommended)

Use the modular package; the old monolithic workflow has been removed.

## Import order

0. `00_RESET_AGENT_APP_V4_2.json` — optional DEV-only reset of `agent_app`; never resets n8n.
1. `01_SETUP_CONFIG_V4_2.json` — application schema/bootstrap + Control Spreadsheet setup.
2. `01B_CONTROL_SYNC_V4_2.json` — Control Spreadsheet -> PostgreSQL sync, including AI prompts/models.
3. `01C_OPERATIONS_INIT_V4_2.json` — per-account Operations Spreadsheet creation/reconciliation.
4. `02_CATALOG_SYNC_V4_2.json` — Products + FAQ + product media catalog sync.
5. `03_HUMAN_CONTROL_V4_2.json` — HumanSupportQueue control.
6. `01D_SYSTEM_HEALTH_V4_2.json` — system checks.
7. `04_FOLLOWUP_V4_2.json` — follow-up worker.
8. `05_META_MESSAGING_V4_2.json` — Meta webhook/message runtime.

## PostgreSQL credential

Every project Postgres node must use one credential with:

```text
Host: postgres
Port: 5432
Database: agent_app
User: n8n (or POSTGRES_USER)
Password: POSTGRES_PASSWORD
SSL: off locally
```

Do not point project workflows at database `n8n`. n8n's own internal database is configured separately by `DB_POSTGRESDB_*` environment variables.

## Activation

Start production workflows inactive. Run setup -> control sync -> operations init -> catalog sync -> health check manually. Publish schedules/webhooks only after the checks pass.

The reset workflow is intentionally separate and must remain inactive; use it only when you explicitly need to wipe AI Commerce application data.
