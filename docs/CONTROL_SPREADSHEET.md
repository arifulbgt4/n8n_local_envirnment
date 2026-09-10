# Control Spreadsheet

Step 02 turns the one empty spreadsheet into the control plane.

## Tabs created automatically

- `00_INSTALL`
- `01_BUSINESSES`
- `02_ACCOUNTS`
- `03_AI_PROMPTS`
- `04_AI_MODELS`
- `05_SYNC_STATUS`
- `06_EXECUTION_LOG`

## `01_BUSINESSES` columns

`Business Key | Business Name | Delivery Charge | Payment Methods | Default AI Prompt | Active | Updated At`

Example:

`shari_ghor | Shari Ghor | 80 | Cash on Delivery | Reply in the customer's language. Never guess price. | TRUE |`

`Business Key` is your internal business identifier. It is not a Facebook Page ID.

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


`AI Provider`, `AI Model`, and `AI Prompt Override` are intentionally not part of `02_ACCOUNTS`. Prompts are configured only in `03_AI_PROMPTS`; provider/model/API-key configuration is only in `04_AI_MODELS`. Existing older sheets may still show those legacy columns, but Control Sync ignores them.

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


## 03_AI_PROMPTS — account-scoped AI prompt registry

All runtime AI prompt text is controlled from this tab. n8n contains no fallback/default business prompt text.

Columns:

`Account Key | Prompt Key | Prompt Text | Active | Updated At | Notes`

Each account can have any number of prompt rows. `Prompt Key` is normalized to uppercase underscore form. Current runtime keys are:


- `INTENT_CLASSIFIER`
- `IMAGE_PRODUCT_ANALYSIS`
- `AUDIO_TRANSCRIPTION`
- `PRODUCT_SEARCH_RESPONSE`
- `ORDER_DETAILS_EXTRACT_AI`
- `GENERAL_ANSWER_AI`

Prompt text supports safe placeholders such as `{{message}}`, `{{conversationState}}`, `{{businessName}}`, `{{inputSource}}`, `{{products}}`, `{{context}}`, or nested paths such as `{{context.selected_product}}`. Objects and arrays are rendered as JSON. Arbitrary JavaScript expressions are intentionally not evaluated.

There is no cross-account or n8n fallback. If a required active prompt is missing, the AI call stops with a configuration error naming the missing `Prompt Key` and account. Updating, disabling, or deleting a prompt row is synced into PostgreSQL by `01B Control Spreadsheet Sync`, and affected response-cache rows are invalidated so the new prompt takes effect.

## 04_AI_MODELS — account-scoped provider/model/API-key registry

All AI provider, model and API-key selection is controlled from this tab. There is no fixed OpenAI/Gemini/Anthropic credential or model fallback inside n8n.

Columns:

`Account Key | Config Key | Provider | Model | API Key | Base URL | Active | Updated At | Notes`

`Config Key=DEFAULT` is an optional account-local default. A task-specific row overrides it. Supported task keys are the prompt keys (`INTENT_CLASSIFIER`, `PRODUCT_SEARCH_RESPONSE`, `ORDER_DETAILS_EXTRACT_AI`, `GENERAL_ANSWER_AI`, `IMAGE_PRODUCT_ANALYSIS`, `AUDIO_TRANSCRIPTION`).

Supported provider adapters: `openai`, `anthropic`, `gemini`, and `openai_compatible`. `openai_compatible` requires `Base URL`. Provider aliases such as `google`/`google_gemini` and `claude` are normalized during sync.

Example: one Page can use `DEFAULT=anthropic`, `IMAGE_PRODUCT_ANALYSIS=gemini`, and `AUDIO_TRANSCRIPTION=openai`; another Page can use a completely different set. If neither an exact task config nor `DEFAULT` exists, the AI call fails with a configuration error instead of silently falling back to any n8n provider/model.

API keys are intentionally sourced from the Control Spreadsheet as requested and are copied into PostgreSQL by `01B Control Spreadsheet Sync`. Restrict the Control Spreadsheet, PostgreSQL database, and n8n execution-data access to trusted administrators because these are secrets.
