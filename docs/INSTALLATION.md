# Fresh-machine installation

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
docker exec -it n8n-postgres psql -U n8n -d postgres -c '\l'
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


## Google Sheets transient connection resets

Control-tab creation is verification-driven. After a create attempt, n8n re-reads spreadsheet metadata and retries only tabs that are still missing, for at most three verified attempts. This safely recovers when Google closes a TLS socket and also avoids duplicate-sheet errors when a create request succeeded but its HTTP response was lost.
