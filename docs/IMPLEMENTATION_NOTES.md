# Implementation notes

Workflow export contains **170 nodes**. Connection references were validated during generation. Imported credentials are intentionally not embedded; bind the Postgres and Google OAuth credentials after import. Live Meta/Google/OpenAI end-to-end testing is still required in your own n8n instance because repository generation cannot validate external account permissions or live tokens.
