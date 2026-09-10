# n8n AI Commerce Automation V4.2

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
