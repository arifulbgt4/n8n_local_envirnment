# PostgreSQL and Docker architecture

## Final database layout

One PostgreSQL Docker container hosts two completely separate databases:

```text
n8n-postgres
├── n8n       -> n8n owner account, workflows, credentials, executions
└── agent_app -> AI Commerce businesses, products, orders, conversations, prompts, model config
```

There is no second PostgreSQL server. Database separation gives the application reset a hard boundary: the reset workflow is connected to `agent_app` and its SQL also checks `current_database()` before any destructive statement.

## Automatic `agent_app` creation

`docker compose up -d` starts `postgres`, then the one-shot `agent-db-bootstrap` service. The bootstrap executes `init-db/001-init.sql`, which:

1. creates `agent_app` only when it does not exist;
2. connects to `agent_app`;
3. creates or upgrades the AI Commerce schema idempotently.

The bootstrap runs on normal Compose startup, so an older existing `n8n_postgres_data` volume is supported. You do **not** need to delete the PostgreSQL volume just to obtain `agent_app`.

## `.env`

Keep these roles separate:

```env
POSTGRES_DB=n8n
DB_POSTGRESDB_DATABASE=n8n
AGENT_DB_NAME=agent_app
```

`DB_POSTGRESDB_*` belongs to n8n itself. Do not change `DB_POSTGRESDB_DATABASE` to `agent_app`.

## n8n Postgres credential for AI Commerce

Create one n8n credential named `AI Agent PostgreSQL`:

```text
Host: postgres
Port: 5432
Database: agent_app
User: n8n               (or POSTGRES_USER from your .env)
Password: POSTGRES_PASSWORD from your .env
SSL: disabled for local Docker
```

The database name is exactly lowercase `agent_app`. `AgentDB`, `agentdb`, and `n8n` are different database names.

If you connect from a desktop database client running on the host instead of from n8n, use `127.0.0.1` as Host and port `5432`.

## Verify both databases

```bash
docker compose up -d
docker compose ps

docker exec -it n8n-postgres psql -U n8n -d postgres -c '\l'
docker exec -it n8n-postgres psql -U n8n -d agent_app -c "SELECT current_database(), to_regclass('public.products');"
```

Expected second command result includes `agent_app` and `products`.

If `agent_app` is missing, inspect:

```bash
docker compose logs agent-db-bootstrap
docker compose logs postgres
```

A successful bootstrap container exits with code `0`; this is expected for a one-shot service.

## Safe restart versus destructive volume deletion

Normal restart:

```bash
docker compose down
docker compose up -d
```

Do **not** use `docker compose down -v` for routine restarts. `-v` deletes the named PostgreSQL, n8n, and product-media volumes and can destroy the n8n owner account and credentials.

## Reset only AI Commerce data

Import `workflows/modular/00_RESET_AGENT_APP_V4_2.json` and attach `AI Agent PostgreSQL` to its Postgres node.

The reset workflow:

- requires the literal confirmation `RESET_AGENT_APP_DATABASE`;
- verifies `current_database() = 'agent_app'` inside PostgreSQL;
- drops/recreates only `agent_app.public`;
- rebuilds the application schema;
- never drops the `n8n` database.

Even if the Postgres credential is accidentally pointed at `n8n`, the SQL guard throws an exception before `DROP SCHEMA` executes.

After a reset, run Setup/Control Sync/Operations Init/Catalog Sync to repopulate configuration and catalog data from the configured spreadsheets.
