# n8n AI Customer Support & Order Management V4

This repository contains the local Docker environment, PostgreSQL schema, one importable n8n workflow, and complete setup documentation for a spreadsheet-driven AI customer-support and order-management system.

Active channels: **Facebook Messenger, Instagram, WhatsApp Cloud API**. TikTok, IMO, custom dashboard, and CRM are not part of this version.

## Core installation rule

At system bootstrap, the **only business runtime input** is one empty **Control Google Spreadsheet ID**.

After bootstrap, the Control Spreadsheet becomes the registry for every business/page/account. Each account row can point to its own Operations Spreadsheet containing `Products`, `FAQ`, `Orders`, `HumanSupportQueue`, `HumanSupportLatest`, and `_System`.

## Repository entry points

1. Read [`docs/INSTALLATION.md`](docs/INSTALLATION.md) on a fresh computer.
2. Import [`workflows/AI_CUSTOMER_SUPPORT_V4_COMPLETE.json`](workflows/AI_CUSTOMER_SUPPORT_V4_COMPLETE.json) into n8n.
3. Follow the exact numbered execution order in [`docs/WORKFLOW_EXECUTION.md`](docs/WORKFLOW_EXECUTION.md).
4. Configure the Control Spreadsheet using [`docs/CONTROL_SPREADSHEET.md`](docs/CONTROL_SPREADSHEET.md).
5. Configure Google OAuth using [`docs/GOOGLE_SETUP.md`](docs/GOOGLE_SETUP.md).
6. Configure Meta using [`docs/META_SETUP.md`](docs/META_SETUP.md).

## Final numbered n8n actions

- `01 - RESET - Entire AI Agent Database (DEV ONLY)`
- `02 - INSTALL - Bootstrap System (ONLY input: Control Spreadsheet ID)`
- `03 - SYNC - Control Spreadsheet -> PostgreSQL`
- `04 - INIT - Account Operations Spreadsheets`
- `05 - SYNC - Products + FAQ Catalog`
- `06 - SYNC - Human Control From Sheets`
- `07 - TEST - System Health`
- `08 - FOLLOW-UP - Manual Test`

Production triggers are separately labeled `PROD - ...`.

## Important behavior

Human handoff is **silent**: when AI decides a customer genuinely needs a human, the conversation moves to HUMAN mode, the support queue is updated, and no automatic handoff acknowledgement is sent. While HUMAN, customer messages update the queue but do not call AI. A manual Facebook Page reply switches the conversation to HUMAN unless the echo message ID matches a bot/API outbound ID. Changing `Mode` to `AI` in `HumanSupportQueue` resumes AI.

## Security

The Control Spreadsheet can contain Meta access tokens because this design is intentionally spreadsheet-driven. Treat it as a secrets-bearing document: restrict sharing, enable account MFA, and rotate exposed tokens. Never commit real tokens, app secrets, Google credentials, database passwords, or `.env` to GitHub.

<!-- V4.2-MODULAR-START -->
## V4.2 modular workflow package

For normal use, import the five files under `workflows/modular/` instead of opening the 170+ node monolith. This reduces editor-side memory/rendering pressure and isolates setup, catalog sync, human control, follow-ups, and Meta messaging. See `docs/MODULAR_WORKFLOWS.md` for the exact import/activation order.

The legacy `workflows/AI_CUSTOMER_SUPPORT_V4_COMPLETE.json` remains available for compatibility, but should not be active at the same time as the modular workflows.
<!-- V4.2-MODULAR-END -->
