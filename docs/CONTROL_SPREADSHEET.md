# Control Spreadsheet

Step 02 turns the one empty spreadsheet into the control plane.

## Tabs created automatically

- `00_INSTALL`
- `01_BUSINESSES`
- `02_ACCOUNTS`
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
