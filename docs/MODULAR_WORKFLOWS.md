# V4.2 Modular Workflows (recommended)

The previous single workflow contains 170+ nodes and can put heavy pressure on the browser editor. V4.2 keeps the corrected monolith for compatibility, but the recommended setup is now split into five smaller importable workflows.

## Import order

1. `01_SETUP_CONFIG_V4_2.json` — reset, bootstrap/install, control-sheet sync, account spreadsheet initialization, health check.
2. `02_CATALOG_SYNC_V4_2.json` — Products + FAQ migration/sync and catalog schedule.
3. `03_HUMAN_CONTROL_V4_2.json` — HumanSupportQueue sheet control and schedule.
4. `04_FOLLOWUP_V4_2.json` — manual follow-up test and production follow-up schedule.
5. `05_META_MESSAGING_V4_2.json` — Meta webhook verification + Facebook/Instagram/WhatsApp message handling.

## Important

- Deactivate the old monolithic workflow before activating the modular workflows. Otherwise duplicate schedules/webhooks can conflict.
- After import, manually select the required Postgres, Google Sheets, and OpenAI credentials in each workflow.
- Importing a JSON file does not automatically replace an already-imported n8n workflow. Import these as new workflows, verify them, then remove/deactivate the old monolith.
- The bootstrap bug in `02.03 - Store Control Spreadsheet ID` is fixed: it now reads the validated ID directly from `02.01 - Validate Control Spreadsheet ID`, so the Postgres schema step cannot turn the spreadsheet ID into `null`.
- Reset remains `$env`-free and requires the explicit confirmation node.

## Activation

Start with all five workflows inactive. Run setup steps 02 → 03 → 04 manually, then catalog/human sync and health checks. Activate the production schedules/webhooks only after credentials and IDs are verified.
