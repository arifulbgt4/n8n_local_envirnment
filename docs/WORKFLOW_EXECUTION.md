# Exact n8n execution order

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
