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

---

# Exact n8n execution order

After importing the workflow and binding credentials, use this order.

## 01 - RESET - Entire AI Agent Database (DEV ONLY)

Not required for normal upgrades. This is destructive to the dedicated `agent_app` database only.

To deliberately enable it, set in `.env`:


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

---

# Control Spreadsheet

Step 02 turns the one empty spreadsheet into the control plane.

## Tabs created automatically

- `00_INSTALL`
- `01_BUSINESSES`
- `02_ACCOUNTS`
- `05_SYNC_STATUS`
- `06_EXECUTION_LOG`

## `01_BUSINESSES` columns

`Business Key | Business Name | Delivery Charge | Payment Methods | Active | Updated At`

Example:

`shari_ghor | Shari Ghor | 80 | Cash on Delivery | TRUE |`

`Business Key` is your internal business identifier. It is not a Facebook Page ID.

Business-level AI prompt text is intentionally not stored in `01_BUSINESSES`. Configure all runtime prompts per account in `03_AI_PROMPTS`.

## `02_ACCOUNTS` columns

1. Account Key
2. Business Key
3. Platform
4. Account Name
5. External Account ID
6. Meta App ID
7. Facebook Page ID
8. Instagram Account ID
9. WhatsApp Phone Number ID
10. WhatsApp Business Account ID
11. Meta App Secret
12. Access Token
13. Verify Token
14. Operations Spreadsheet ID
15. Auto Create Spreadsheet
16. Graph API Version
17. Reply URL
18. Conversation URL Template
19. Max Messages Per Minute
20. Max AI Turns Per Hour
21. Max AI Turns Per Day
22. Estimated Tokens Per Turn
23. Max Estimated Tokens Per Day
24. Followup Enabled
25. Followup 1 Minutes
26. Followup 2 Minutes
27. Auto Human On Manual Reply
28. Active
29. Updated At

## Platform identity rules

Facebook Messenger: `External Account ID` = Facebook Page ID / incoming `recipient.id`.

Instagram: `External Account ID` = the receiving Instagram professional account identifier used by the webhook normalization.

WhatsApp: `External Account ID` = `metadata.phone_number_id`.

Never use the parent `Business Key` as a Page ID.

## Operations Spreadsheet ID

Recommended: one Operations Spreadsheet per Page/account. Put that spreadsheet ID in column 14.

If it is blank and `Auto Create Spreadsheet=TRUE`, Step 04 can create a new spreadsheet and write its new ID back to the Control Spreadsheet.

## Tokens and secrets

This architecture supports Meta tokens in the Control Spreadsheet because you requested spreadsheet-driven account administration. Restrict the file to trusted administrators only. A Page Access Token is not the same thing as a Verify Token or App Secret.

---

# Per-account Operations Spreadsheet

Step 04 ensures the following tabs exist for every active account:

- `Products`
- `FAQ`
- `Orders`
- `HumanSupportQueue`
- `HumanSupportLatest`
- `_System`

The merchant normally edits only `Products` and `FAQ`.

## Canonical Products columns

`Product ID | Product Name | Category | Subcategory | Price | Currency | Product Description | Product Image | Stock Status | Stock Qty | Color | Size | Offer | Discount | Aliases | Active | Updated At`

Legacy headers are recognized during catalog sync, including:

- `Product Name`
- `Price (৳)`
- `Product Description`
- `Product Image`
- `Stock Status`

Blank `Stock Status` means unknown; it must not be converted to out-of-stock.

If a recognized legacy Products sheet is detected, Step 05 first creates a timestamped `Products_BACKUP_...` tab, rewrites `Products` into the canonical columns, deduplicates exact repeated products, and sorts by Category/Subcategory/Product Name. It then syncs the canonical data into PostgreSQL. The workflow preserves factual values and never invents a price. Embedded Google Sheets images are not reliable API image URLs; put an explicit public/accessible image URL or Drive-backed URL in `Product Image`.

## HumanSupportQueue columns

`Conversation ID | Business ID | Business Name | Platform | Account ID | Customer ID | Customer External ID | Latest Customer Message | Latest Message Time | Conversation URL | Mode | Handoff Reason | Handoff Source | Status | Updated At`

One conversation should keep one queue row. `Mode=HUMAN` stops AI. Change it to `AI` and Step/production human-control sync resumes AI.

`HumanSupportLatest` is a newest-first view of the queue.

---

# Google Sheets authentication

Google Sheets access uses Google OAuth2/Google Sheets credentials in n8n. It is not a Gmail sending token.

1. Create/select a Google Cloud project.
2. Enable Google Sheets API. Enable Google Drive API too if you later add Drive file operations.
3. Configure the OAuth consent screen.
4. Create an OAuth Client ID for a Web application.
5. In n8n, create a Google Sheets OAuth2 credential and copy n8n's OAuth redirect URL into the Google client's Authorized redirect URIs.
6. Authorize the Google account that owns or can edit the Control Spreadsheet and account Operations Spreadsheets.
7. Attach this same credential to every Google API HTTP Request node in the workflow.

The one installation runtime input remains only the Control Spreadsheet ID; OAuth is configured once beforehand.

---

# Meta setup: Facebook Messenger, Instagram, WhatsApp

## Shared callback

Use one public HTTPS callback:

`https://YOUR-PUBLIC-DOMAIN/webhook/meta-commerce`

The workflow exposes both:

- GET `/webhook/meta-commerce` for verification
- POST `/webhook/meta-commerce` for events

The GET verifier looks up the incoming `hub.verify_token` against active account rows synced from the Control Spreadsheet and returns `hub.challenge` only when valid.

## Facebook Messenger

For each Page, record separately in `02_ACCOUNTS`:

- Page ID
- Page Access Token
- Verify Token
- Meta App ID
- App Secret if you choose to store it
- Operations Spreadsheet ID

A Facebook Page ID such as `1347372081785892` is an external account ID, not your application's business ID.

Subscribe the Page/app to the messaging webhook fields needed by your use case. Enable message echoes if you want manual Page replies to switch conversations to HUMAN. The runtime stores bot outbound message IDs so bot echoes are ignored while real Page-owner messages can switch to HUMAN.

## Instagram

Use an Instagram professional account supported by the Meta messaging API you configure. Store its receiving account identifier and token on its own account row. Do not assume the Facebook Page ID and Instagram account ID are interchangeable.

## WhatsApp Cloud API

Store the WhatsApp `phone_number_id` as `External Account ID`, plus WABA ID and access token on the account row.

## Development vs public customers

Testing with app roles/test users can work before public release. Real non-role customers require the appropriate Meta app mode, product configuration, permissions/access level, and—when Meta requires it—App Review and/or Business Verification.

Meta changes its dashboard and review requirements over time. Prepare a clear use-case explanation, test instructions, privacy policy/data-deletion information if requested, and a screencast when the review flow asks for one. Do not treat n8n workflow publication as equivalent to Meta App Review approval.

---

# Architecture

Control Spreadsheet -> PostgreSQL configuration -> account-specific Operations Spreadsheets -> webhook runtime.

Each `businesses` row is a parent business. Each `business_accounts` row is one Facebook Page, Instagram account, or WhatsApp phone number. Runtime routing uses `(platform, external_account_id)` to select the correct account and token, while retaining the parent business association.

Products/FAQ are account-scoped because each Page/account can have a different Operations Spreadsheet.

Human handoff is DB-backed and sheet-controlled. Facebook `message_echoes` are checked against `bot_outbound_messages` so AI/API echoes are ignored while a real Page-owner reply can switch the conversation to HUMAN.

---

# Security and abuse protection

## AI cost guard order

Before expensive AI/media calls, the runtime should enforce:

1. webhook message dedupe
2. bot-echo filtering
3. HUMAN-mode guard
4. per-customer messages/minute
5. repeated-message protection
6. AI turns/hour
7. AI turns/day
8. estimated daily token budget
9. response cache / deterministic routing when possible
10. only then transcription, vision, or LLM calls

Blocked spam is not automatically escalated to HUMAN.

## Human handoff

Customer receives no automatic “sent to human support” message. AI handoff writes DB + HumanSupportQueue and stops silently.

## Secrets

Never commit `.env` or real credentials. This project allows Meta tokens in the Control Spreadsheet because spreadsheet-driven administration is a product requirement. Treat the sheet as sensitive infrastructure and limit access.

---

# Troubleshooting

## Meta verification returns 403

Run Step 03 first. Confirm the account is Active and its Verify Token exactly matches the token entered in Meta.

## Incoming customer message finds no account

Compare the webhook receiving identifier with `02_ACCOUNTS -> External Account ID`:

- Facebook: Page ID / recipient.id
- WhatsApp: metadata.phone_number_id
- Instagram: receiving Instagram account identifier used by your webhook payload

## Product price becomes 0

Confirm your sheet header is recognized. `Price (৳)` is supported by the normalization design; do not replace missing prices with guessed values.

## AI stops replying after a human message

Check `HumanSupportQueue -> Mode`. If it is `HUMAN`, set it to `AI` and run Step 06 or wait for the production human-control schedule.

## Bot replies switch to HUMAN by mistake

Confirm the send-message response message ID is being stored in `bot_outbound_messages`; Page echo detection must compare echo `message_id` against this table.

## n8n shows localhost webhook URL

Set `N8N_WEBHOOK_URL` to your public HTTPS ngrok/domain URL, restart the containers, then re-open the Webhook node.

---

# Implementation notes

Workflow export contains **170 nodes**. Connection references were validated during generation. Imported credentials are intentionally not embedded; bind the Postgres and Google OAuth credentials after import. Live Meta/Google/OpenAI end-to-end testing is still required in your own n8n instance because repository generation cannot validate external account permissions or live tokens.

<!-- V4.2-MODULAR-START -->
## V4.2 modular workflow package

For normal use, import the five files under `workflows/modular/` instead of opening the 170+ node monolith. This reduces editor-side memory/rendering pressure and isolates setup, catalog sync, human control, follow-ups, and Meta messaging. See `docs/MODULAR_WORKFLOWS.md` for the exact import/activation order.

The legacy `workflows/AI_CUSTOMER_SUPPORT_V4_COMPLETE.json` remains available for compatibility, but should not be active at the same time as the modular workflows.
<!-- V4.2-MODULAR-END -->
