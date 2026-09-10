# Fresh-machine installation

## 1. Install prerequisites

Install Git and Docker Desktop (Windows/macOS) or Docker Engine + Compose plugin (Linux). Confirm:

```bash
git --version
docker --version
docker compose version
```

## 2. Clone the repository

```bash
git clone https://github.com/arifulbgt4/n8n_local_envirnment.git
cd n8n_local_envirnment
cp .env.example .env
```

Edit `.env`. At minimum change `POSTGRES_PASSWORD` and `N8N_ENCRYPTION_KEY`.

## 3. Start PostgreSQL + n8n

```bash
docker compose up -d
```

Open `http://localhost:5678` and create the n8n owner account.

The Docker init script creates two databases:

- `n8n` - n8n internal state
- `agent_app` - this project's customer/order/application data

## 4. Create n8n credentials once

Create a Postgres credential named `AI Agent PostgreSQL`:

- Host: `postgres`
- Port: `5432`
- Database: `agent_app`
- User: value of `POSTGRES_USER`
- Password: value of `POSTGRES_PASSWORD`
- SSL: off for local Docker

Create a Google Sheets OAuth2 credential as documented in `GOOGLE_SETUP.md`. Attach that same Google credential to every Google API HTTP Request node in the imported workflow.

Attach `AI Agent PostgreSQL` to every Postgres node.

## 5. Import the workflow

Import:

`workflows/AI_CUSTOMER_SUPPORT_V4_COMPLETE.json`

Do not publish yet. Bind the Postgres and Google credentials first.

## 6. Create one empty Control Spreadsheet

Create one blank Google Spreadsheet in the Google account connected to n8n. Copy its ID from the URL.

Do not manually create tabs. Step 02 creates them.

## 7. Run numbered workflow steps

Follow `WORKFLOW_EXECUTION.md` exactly.

## 8. ngrok for local Meta callbacks

Install ngrok, authenticate once, then run:

```bash
ngrok http 5678
```

Copy the HTTPS forwarding URL, set it in `.env`:

```env
N8N_WEBHOOK_URL=https://YOUR-NGROK-DOMAIN/
```

Restart n8n:

```bash
docker compose down
docker compose up -d
```

Meta callback URL:

`https://YOUR-NGROK-DOMAIN/webhook/meta-commerce`

GET verification and POST events use the same path, differentiated by HTTP method.

A free/ephemeral ngrok URL may change after restart. If it changes, update `N8N_WEBHOOK_URL`, restart n8n, and update the Meta callback.
