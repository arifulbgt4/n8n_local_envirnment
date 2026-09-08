# Exact n8n execution order

After importing the workflow and binding credentials, use this order.

## 01 - RESET - Entire AI Agent Database (DEV ONLY)

Not required for normal upgrades. This is destructive to the dedicated `agent_app` database only.

To deliberately enable it, set in `.env`:

`ALLOW_DESTRUCTIVE_RESET=RESET_AI_AGENT_DATABASE`

Restart n8n, execute the step, then immediately clear the variable and restart again.

## 02 - INSTALL - Bootstrap System

Only runtime input: `Control Spreadsheet ID`.

Expected result: DB schema exists, Control Spreadsheet ID is stored in `system_settings`, and control tabs/headers are created without deleting existing valid data.

## 03 - SYNC - Control Spreadsheet -> PostgreSQL

Read `01_BUSINESSES` and `02_ACCOUNTS`, validate rows, then upsert parent businesses and child platform accounts.

## 04 - INIT - Account Operations Spreadsheets

For each active account, use its Operations Spreadsheet ID. If blank and `Auto Create Spreadsheet=TRUE`, create one and write the new ID back to `02_ACCOUNTS`. Ensure Products, FAQ, Orders, HumanSupportQueue, HumanSupportLatest, and _System exist.

## 05 - SYNC - Products + FAQ Catalog

For each account, recognized legacy Products sheets are backed up, normalized to the canonical columns, deterministically categorized, deduplicated, and sorted. Then Products + FAQ sync into PostgreSQL. Prices remain source-controlled and are never guessed.

## 06 - SYNC - Human Control From Sheets

Read HumanSupportQueue rows. `Mode=HUMAN` disables AI; `Mode=AI` resumes AI and resolves pending handoff state.

## 07 - TEST - System Health

Checks installation ID, active accounts, spreadsheet IDs, products, FAQ rows, and unresolved HUMAN conversations.

## 08 - FOLLOW-UP - Manual Test

Runs only due follow-ups using the same production guards. Do not send follow-ups in HUMAN mode.

## Production triggers

After the setup tests pass, publish the workflow. Production triggers are labeled:

- `PROD - Meta Webhook Verify GET`
- `PROD - Meta Webhook POST`
- `PROD - Control Config Sync Schedule`
- `PROD - Catalog Sync Schedule`
- `PROD - Human Control Sync Schedule`
- `PROD - Follow-up Schedule`
