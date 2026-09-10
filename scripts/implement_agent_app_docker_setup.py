import json
from pathlib import Path

ROOT = Path('.')

# -----------------------------------------------------------------------------
# Docker Compose: one PostgreSQL server, two databases. A one-shot bootstrap
# service runs on every compose startup so existing postgres volumes also gain
# agent_app and all required application tables without touching n8n tables.
# -----------------------------------------------------------------------------
compose = '''services:
  postgres:
    image: postgres:17-alpine
    container_name: n8n-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      TZ: ${TZ}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 20

  agent-db-bootstrap:
    image: postgres:17-alpine
    container_name: n8n-agent-db-bootstrap
    restart: "no"
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
      PGHOST: postgres
      PGPORT: 5432
      PGUSER: ${POSTGRES_USER}
      PGPASSWORD: ${POSTGRES_PASSWORD}
      TZ: ${TZ}
    volumes:
      - ./init-db:/bootstrap:ro
    entrypoint: ["/bin/sh", "-c"]
    command:
      - >
        psql -d "$${POSTGRES_DB}" -v ON_ERROR_STOP=1 -f /bootstrap/001-init.sql

  media-cache:
    build:
      context: ./services/media-cache
    container_name: n8n-media-cache
    restart: unless-stopped
    environment:
      PORT: 3001
      CACHE_DIR: /data/product-media
      MAX_IMAGE_BYTES: ${PRODUCT_MEDIA_CACHE_MAX_BYTES:-26214400}
      GRAPH_VERSION: v26.0
      TZ: ${TZ}
    ports:
      - "127.0.0.1:3001:3001"
    volumes:
      - product_media_cache:/data/product-media
    healthcheck:
      test: ["CMD", "node", "-e", "fetch('http://127.0.0.1:3001/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
      interval: 10s
      timeout: 5s
      retries: 10

  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      agent-db-bootstrap:
        condition: service_completed_successfully
      media-cache:
        condition: service_healthy
    ports:
      - "127.0.0.1:5678:5678"
    env_file:
      - .env
    volumes:
      - n8n_data:/home/node/.n8n

volumes:
  n8n_data:
    name: n8n_data
  postgres_data:
    name: n8n_postgres_data
  product_media_cache:
    name: n8n_product_media_cache
'''
(ROOT / 'docker-compose.yml').write_text(compose, encoding='utf-8')

env_example = '''# Copy this file to .env and change every CHANGE_ME value.
# PostgreSQL server/admin settings. The n8n internal database remains `n8n`.
POSTGRES_USER=n8n
POSTGRES_PASSWORD=CHANGE_ME_STRONG_POSTGRES_PASSWORD
POSTGRES_DB=n8n

# AI Commerce application database. This is intentionally separate from n8n.
# The Docker bootstrap service creates `agent_app` automatically.
AGENT_DB_HOST=postgres
AGENT_DB_PORT=5432
AGENT_DB_NAME=agent_app
AGENT_DB_USER=n8n
AGENT_DB_PASSWORD=CHANGE_ME_STRONG_POSTGRES_PASSWORD

TZ=Asia/Dhaka
GENERIC_TIMEZONE=Asia/Dhaka

# n8n internal database. Do NOT point these variables at agent_app.
DB_TYPE=postgresdb
DB_POSTGRESDB_HOST=postgres
DB_POSTGRESDB_PORT=5432
DB_POSTGRESDB_DATABASE=n8n
DB_POSTGRESDB_USER=n8n
DB_POSTGRESDB_PASSWORD=CHANGE_ME_STRONG_POSTGRES_PASSWORD

# Persistent encryption key for n8n credentials. Never change it casually.
N8N_ENCRYPTION_KEY=CHANGE_ME_LONG_RANDOM_VALUE
N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
N8N_RUNNERS_ENABLED=true
N8N_SECURE_COOKIE=false

# Public URL used by Meta webhooks when using ngrok/reverse proxy.
# Example: https://your-static-domain.ngrok-free.app/
N8N_WEBHOOK_URL=
N8N_PROXY_HOPS=1

# Persistent local product image cache (25 MiB per image by default)
PRODUCT_MEDIA_CACHE_MAX_BYTES=26214400
'''
(ROOT / '.env.example').write_text(env_example, encoding='utf-8')

# Make the existing init script safe and idempotent. It now works both during
# first-volume initialization and from the recurring one-shot bootstrap service.
init_path = ROOT / 'init-db/001-init.sql'
init_sql = init_path.read_text(encoding='utf-8')
old_prefix = "-- Runs only when the PostgreSQL Docker volume is created for the first time.\n-- n8n uses database `n8n`; the AI application uses a separate database `agent_app`.\nCREATE DATABASE agent_app;\n\\connect agent_app\n"
new_prefix = """\\set ON_ERROR_STOP on
-- Safe to run during first PostgreSQL volume initialization and on later Docker starts.
-- n8n uses database `n8n`; the AI application uses the separate database `agent_app`.
-- CREATE DATABASE cannot use IF NOT EXISTS, so psql \\gexec executes it only when missing.
SELECT 'CREATE DATABASE agent_app'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'agent_app')
\\gexec
\\connect agent_app
"""
if old_prefix in init_sql:
    init_sql = init_sql.replace(old_prefix, new_prefix, 1)
elif not init_sql.startswith('\\set ON_ERROR_STOP on'):
    raise RuntimeError('Unexpected init-db/001-init.sql prefix; refusing unsafe rewrite')
init_path.write_text(init_sql, encoding='utf-8')

# Add a database-name guard to the standalone destructive reset SQL.
reset_path = ROOT / 'docs/RESET_APPLICATION_DATABASE.sql'
reset_sql = reset_path.read_text(encoding='utf-8')
if 'current_database()' not in reset_sql[:1200]:
    marker = '-- DANGEROUS: run only against the dedicated agent_app database.\n'
    guard = marker + """-- Hard safety guard: this script refuses to run against n8n or any other database.
DO $agent_reset_guard$
BEGIN
  IF current_database() <> 'agent_app' THEN
    RAISE EXCEPTION 'SAFETY STOP: connected database is %, expected agent_app. n8n was not modified.', current_database();
  END IF;
END
$agent_reset_guard$;

"""
    if not reset_sql.startswith(marker):
        raise RuntimeError('Unexpected reset SQL header')
    reset_sql = reset_sql.replace(marker, guard, 1)
reset_path.write_text(reset_sql, encoding='utf-8')

# Dedicated reset workflow. It never drops a database: it only resets public
# schema inside agent_app, and the SQL itself verifies current_database first.
workflow_query = reset_sql
reset_workflow = {
    'name': 'AI Commerce V4.2 - 00 Reset Agent App Database',
    'nodes': [
        {
            'parameters': {},
            'id': '00-reset-manual-trigger',
            'name': '01 - RESET - Agent App Database (DEV ONLY)',
            'type': 'n8n-nodes-base.manualTrigger',
            'typeVersion': 1,
            'position': [-600, 0],
        },
        {
            'parameters': {
                'jsCode': "const reset_confirmation = 'CHANGE_ME__TYPE_RESET_AGENT_APP_DATABASE';\nif (reset_confirmation !== 'RESET_AGENT_APP_DATABASE') {\n  throw new Error('SAFETY STOP: edit this node and set reset_confirmation exactly to RESET_AGENT_APP_DATABASE, then change it back after the reset.');\n}\nreturn [{json:{reset_confirmation}}];"
            },
            'id': '00-reset-confirmation',
            'name': '01.00 - Enter Reset Confirmation (EDIT BEFORE RESET)',
            'type': 'n8n-nodes-base.code',
            'typeVersion': 2,
            'position': [-360, 0],
        },
        {
            'parameters': {
                'jsCode': "if ($json.reset_confirmation !== 'RESET_AGENT_APP_DATABASE') throw new Error('SAFETY STOP: invalid reset confirmation.');\nreturn [{json:{...$json, safety_check:'confirmed'}}];"
            },
            'id': '00-reset-safety-guard',
            'name': '01.01 - Reset Safety Guard',
            'type': 'n8n-nodes-base.code',
            'typeVersion': 2,
            'position': [-120, 0],
        },
        {
            'parameters': {
                'operation': 'executeQuery',
                'query': workflow_query,
                'options': {},
            },
            'id': '00-reset-agent-schema',
            'name': '01.02 - Reset + Recreate agent_app Schema',
            'type': 'n8n-nodes-base.postgres',
            'typeVersion': 2.6,
            'position': [120, 0],
        },
        {
            'parameters': {
                'jsCode': "return [{json:{ok:true,database:'agent_app',message:'agent_app application schema reset completed. n8n database was not touched.'}}];"
            },
            'id': '00-reset-result',
            'name': '01.03 - Reset Complete',
            'type': 'n8n-nodes-base.code',
            'typeVersion': 2,
            'position': [360, 0],
        },
    ],
    'pinData': {},
    'connections': {
        '01 - RESET - Agent App Database (DEV ONLY)': {'main': [[{'node': '01.00 - Enter Reset Confirmation (EDIT BEFORE RESET)', 'type': 'main', 'index': 0}]]},
        '01.00 - Enter Reset Confirmation (EDIT BEFORE RESET)': {'main': [[{'node': '01.01 - Reset Safety Guard', 'type': 'main', 'index': 0}]]},
        '01.01 - Reset Safety Guard': {'main': [[{'node': '01.02 - Reset + Recreate agent_app Schema', 'type': 'main', 'index': 0}]]},
        '01.02 - Reset + Recreate agent_app Schema': {'main': [[{'node': '01.03 - Reset Complete', 'type': 'main', 'index': 0}]]},
    },
    'active': False,
    'settings': {'executionOrder': 'v1', 'timezone': 'Asia/Dhaka'},
    'tags': [],
}
(ROOT / 'workflows/modular/00_RESET_AGENT_APP_V4_2.json').write_text(
    json.dumps(reset_workflow, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8'
)

# -----------------------------------------------------------------------------
# Documentation
# -----------------------------------------------------------------------------
db_doc = '''# PostgreSQL and Docker architecture

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

docker exec -it n8n-postgres psql -U n8n -d postgres -c '\\l'
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
'''
(ROOT / 'docs/DATABASES_AND_DOCKER.md').write_text(db_doc, encoding='utf-8')

installation = '''# Fresh-machine installation

## 1. Install prerequisites

Install Git and Docker Desktop (Windows/macOS) or Docker Engine + Compose plugin (Linux):

```bash
git --version
docker --version
docker compose version
```

## 2. Clone and configure

```bash
git clone https://github.com/arifulbgt4/n8n_local_envirnment.git
cd n8n_local_envirnment
cp .env.example .env
```

Edit `.env`. At minimum replace `POSTGRES_PASSWORD`, `AGENT_DB_PASSWORD` with the same PostgreSQL password, and `N8N_ENCRYPTION_KEY`.

Keep the database split unchanged:

```env
POSTGRES_DB=n8n
DB_POSTGRESDB_DATABASE=n8n
AGENT_DB_NAME=agent_app
```

## 3. Start the complete stack

```bash
docker compose up -d
```

Startup order is enforced:

```text
postgres healthy
      ↓
agent-db-bootstrap -> creates/upgrades agent_app -> exits 0
      ↓
media-cache healthy
      ↓
n8n starts
```

Open `http://localhost:5678` and create/login to the n8n owner account.

The same PostgreSQL container contains two databases: `n8n` for n8n itself and `agent_app` for this project. See `DATABASES_AND_DOCKER.md`.

## 4. Verify `agent_app`

```bash
docker compose ps
docker exec -it n8n-postgres psql -U n8n -d postgres -c '\\l'
docker exec -it n8n-postgres psql -U n8n -d agent_app -c "SELECT current_database(), to_regclass('public.products');"
```

`agent-db-bootstrap` showing `Exited (0)` is normal. It is a one-shot initializer.

## 5. Create n8n credentials

Create Postgres credential `AI Agent PostgreSQL`:

- Host: `postgres`
- Port: `5432`
- Database: `agent_app`
- User: `n8n` / your `POSTGRES_USER`
- Password: your `POSTGRES_PASSWORD`
- SSL: off for local Docker

If n8n marks the credential red, first verify that the database field is exactly `agent_app` and run `docker compose logs agent-db-bootstrap`.

Create the Google Sheets OAuth2 credential as documented in `GOOGLE_SETUP.md`. Attach `AI Agent PostgreSQL` to all project Postgres nodes. Do not create a project credential pointing to database `n8n`.

## 6. Import modular workflows

Import the JSON files under `workflows/modular/` following `workflows/modular/README.md`. `00_RESET_AGENT_APP_V4_2.json` is optional and should only be used intentionally in development.

## 7. Control Spreadsheet

Create one blank Google Spreadsheet, copy its ID, then run setup. Do not manually create control tabs; the setup workflow creates them.

Follow `WORKFLOW_EXECUTION.md` for the execution order.

## 8. ngrok for local Meta callbacks

```bash
ngrok http 5678
```

Set the HTTPS URL in `.env`:

```env
N8N_WEBHOOK_URL=https://YOUR-NGROK-DOMAIN/
```

Restart safely:

```bash
docker compose down
docker compose up -d
```

Meta callback:

```text
https://YOUR-NGROK-DOMAIN/webhook/meta-commerce
```

Never use `docker compose down -v` for a routine restart; it removes persistent volumes. See `DATABASES_AND_DOCKER.md`.
'''
(ROOT / 'docs/INSTALLATION.md').write_text(installation, encoding='utf-8')

workflow_execution = '''# Exact n8n execution order

All project Postgres nodes must use the `AI Agent PostgreSQL` credential whose database is exactly `agent_app`. n8n itself continues to use database `n8n` through `.env`.

## Optional 00 - RESET - Agent App Database (DEV ONLY)

Workflow file: `workflows/modular/00_RESET_AGENT_APP_V4_2.json`.

Reset is not required for normal upgrades. It deletes/recreates only the AI Commerce schema inside `agent_app`; it never resets the n8n owner account, workflows or credentials.

1. Attach the `AI Agent PostgreSQL` credential to `01.02 - Reset + Recreate agent_app Schema`.
2. Open `01.00 - Enter Reset Confirmation (EDIT BEFORE RESET)`.
3. Temporarily change `CHANGE_ME__TYPE_RESET_AGENT_APP_DATABASE` to exactly `RESET_AGENT_APP_DATABASE`.
4. Run `01 - RESET - Agent App Database (DEV ONLY)` from the manual trigger.
5. After success, change the literal back to the invalid default and save.

There are two safety layers: the n8n confirmation node and a PostgreSQL `current_database()='agent_app'` guard before `DROP SCHEMA`.

## 01 - Setup / bootstrap

Run `01_SETUP_CONFIG_V4_2.json`. Enter the Control Spreadsheet ID. Expected result: application schema is available and Control Spreadsheet configuration is initialized without destroying n8n state.

## 02 - Control Spreadsheet sync

Run `01B_CONTROL_SYNC_V4_2.json` -> `03 - SYNC - Control Spreadsheet -> PostgreSQL`.

This loads businesses, accounts, account prompts and dynamic AI provider/model configuration into `agent_app`.

## 03 - Operations Spreadsheet initialization/reconciliation

Run `01C_OPERATIONS_INIT_V4_2.json` -> `04 - INIT - Account Operations Spreadsheets`.

Missing Products/FAQ/Orders/support tabs are created. If the database already contains managed account data, DB state restores into a changed Operations Spreadsheet. If managed DB data is zero, the spreadsheet seeds the database.

## 04 - Product + FAQ catalog sync

Run `02_CATALOG_SYNC_V4_2.json` -> catalog sync. Products, variants and up to ten product images are reconciled into PostgreSQL.

## 05 - Human control

Run/import `03_HUMAN_CONTROL_V4_2.json` and verify HumanSupportQueue synchronization.

## 06 - Health

Run `01D_SYSTEM_HEALTH_V4_2.json` and verify accounts, spreadsheet IDs, products and FAQ counts.

## 07 - Follow-up

Run/import `04_FOLLOWUP_V4_2.json`. Follow-ups must not send while a conversation is in HUMAN mode.

## 08 - Meta messaging

Import/publish `05_META_MESSAGING_V4_2.json` only after credentials/configuration tests pass.

Production triggers include Meta webhook GET/POST, control sync, catalog sync, human-control sync and follow-up schedule. Do not activate duplicate copies of the same workflows.
'''
(ROOT / 'docs/WORKFLOW_EXECUTION.md').write_text(workflow_execution, encoding='utf-8')

modular_readme = '''# V4.2 modular workflows (recommended)

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
'''
(ROOT / 'workflows/modular/README.md').write_text(modular_readme, encoding='utf-8')

readme = '''# n8n AI Commerce Automation V4.2

Local Docker environment and modular n8n workflows for spreadsheet-driven Facebook/Instagram/WhatsApp customer support, product catalog, orders, AI prompts and dynamic AI providers.

## Database isolation

A single PostgreSQL container hosts two separate databases:

```text
n8n       -> n8n internal owner/workflow/credential/execution data
agent_app -> AI Commerce application data only
```

`docker compose up -d` automatically creates/upgrades `agent_app` through the one-shot `agent-db-bootstrap` service, including when the PostgreSQL volume already existed. The n8n service waits for that bootstrap to succeed. See `docs/DATABASES_AND_DOCKER.md`.

## Quick start

```bash
git clone https://github.com/arifulbgt4/n8n_local_envirnment.git
cd n8n_local_envirnment
cp .env.example .env
# edit .env
docker compose up -d
```

Then open `http://localhost:5678`.

For AI Commerce Postgres nodes create an n8n credential with `Host=postgres`, `Port=5432`, `Database=agent_app`, and the PostgreSQL username/password from `.env`. Never use the internal `n8n` database for project workflow nodes.

## Documentation

- `docs/INSTALLATION.md` — fresh-machine setup.
- `docs/DATABASES_AND_DOCKER.md` — database isolation, verification and troubleshooting.
- `workflows/modular/README.md` — modular import order.
- `docs/WORKFLOW_EXECUTION.md` — manual setup/test order and safe reset.
- `docs/CONTROL_SPREADSHEET.md` — businesses, accounts, AI prompts and model/provider registry.
- `docs/GOOGLE_SETUP.md` — Google OAuth.
- `docs/META_SETUP.md` — Meta configuration.
- `docs/PRODUCT_CATALOG.md` — products and image/media sync.

## Safe application reset

`workflows/modular/00_RESET_AGENT_APP_V4_2.json` resets only `agent_app`. It has both an explicit confirmation gate and a database-name guard. It never resets n8n accounts/workflows/credentials.

Do not use `docker compose down -v` for normal restarts because `-v` removes persistent volumes.

## Security

The Control Spreadsheet can contain Meta access tokens and AI provider API keys. Restrict it to trusted administrators, use MFA, and never commit real `.env`, credentials, tokens or API secrets.
'''
(ROOT / 'README.md').write_text(readme, encoding='utf-8')

print('agent_app Docker/database migration files written')
