# Architecture

Control Spreadsheet -> PostgreSQL configuration -> account-specific Operations Spreadsheets -> webhook runtime.

Each `businesses` row is a parent business. Each `business_accounts` row is one Facebook Page, Instagram account, or WhatsApp phone number. Runtime routing uses `(platform, external_account_id)` to select the correct account and token, while retaining the parent business association.

Products/FAQ are account-scoped because each Page/account can have a different Operations Spreadsheet.

Human handoff is DB-backed and sheet-controlled. Facebook `message_echoes` are checked against `bot_outbound_messages` so AI/API echoes are ignored while a real Page-owner reply can switch the conversation to HUMAN.
