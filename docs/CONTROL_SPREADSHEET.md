# Control Spreadsheet

Step 02 turns the one empty spreadsheet into the control plane.

## Tabs created automatically

- `00_INSTALL`
- `01_BUSINESSES`
- `02_ACCOUNTS`
- `03_AI_PROMPTS`
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
19. AI Provider
20. AI Model
21. AI Prompt Override
22. Max Messages Per Minute
23. Max AI Turns Per Hour
24. Max AI Turns Per Day
25. Estimated Tokens Per Turn
26. Max Estimated Tokens Per Day
27. Followup Enabled
28. Followup 1 Minutes
29. Followup 2 Minutes
30. Auto Human On Manual Reply
31. Active
32. Updated At

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
- `PRODUCT_SEARCH_RESPONSE`
- `ORDER_DETAILS_EXTRACT_AI`
- `GENERAL_ANSWER_AI`

Prompt text supports safe placeholders such as `{{message}}`, `{{conversationState}}`, `{{businessName}}`, `{{inputSource}}`, `{{products}}`, `{{context}}`, or nested paths such as `{{context.selected_product}}`. Objects and arrays are rendered as JSON. Arbitrary JavaScript expressions are intentionally not evaluated.

There is no cross-account or n8n fallback. If a required active prompt is missing, the AI call stops with a configuration error naming the missing `Prompt Key` and account. Updating, disabling, or deleting a prompt row is synced into PostgreSQL by `01B Control Spreadsheet Sync`, and affected response-cache rows are invalidated so the new prompt takes effect.