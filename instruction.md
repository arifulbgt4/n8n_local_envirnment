# Multi-Platform `businesses` Configuration + Workflow Execution Guide

This guide is for the n8n **AI Customer Support & Order Management** workflow using:

- Facebook Messenger
- Instagram
- WhatsApp Cloud API
- PostgreSQL
- Google Sheets
- AI model nodes

TikTok, IMO, Custom Dashboard, and CRM are intentionally excluded.

The same `businesses` table is reused for every Facebook Page, Instagram account, and WhatsApp number. You do **not** create a new database table for every account.

Each incoming message is matched to the correct `businesses` row by `business_id`. That row determines the correct access token, Google Sheet, product catalog, FAQ, delivery settings, AI instructions, and reply endpoint.

---

# 1. IMPORTANT — Exact workflow execution order

The workflow has multiple triggers. Do **not** execute them randomly the first time.

When n8n shows this trigger dropdown:

```text
from Meta Webhook Verify GET
from Meta Webhook POST
from Setup DB Trigger
from Catalog Sync Schedule
from Follow-up Schedule
```

use the following order.

## Step 1 — Run `from Setup DB Trigger`

This is always the **first execution** after importing the workflow.

Select:

```text
from Setup DB Trigger
```

Then click:

```text
Execute workflow
```

Expected flow:

```text
Setup DB Trigger
      ↓
Setup / Migrate DB
```

Purpose:

- creates/migrates required PostgreSQL tables
- creates `businesses`
- creates product/cache/FAQ/order support tables
- adds `verify_token`
- creates indexes
- enables required database features

Run this before inserting any `businesses` rows.

You may run the migration again because the setup SQL uses safe patterns such as `IF NOT EXISTS` where applicable.

---

## Step 2 — Insert / UPSERT `businesses` rows

After `Setup / Migrate DB` succeeds, add your Facebook / Instagram / WhatsApp configurations to PostgreSQL.

This is **not** a Meta webhook execution.

You can run the UPSERT SQL using:

- a temporary Postgres `Execute Query` node in n8n, or
- your PostgreSQL client / terminal

Recommended temporary node name:

```text
Insert Business Config
```

Recommended connection while setting up:

```text
Setup DB Trigger
      ↓
Setup / Migrate DB
      ↓
Insert Business Config
```

After the rows are inserted, this node does not need to be part of the normal customer-message path.

### Verify the rows immediately

```sql
SELECT
  business_id,
  platform,
  business_name,
  verify_token,
  sheet_document_id,
  product_sheet_name,
  faq_sheet_name,
  order_sheet_name,
  delivery_charge_default,
  payment_methods,
  active
FROM businesses
ORDER BY platform, business_name;
```

Do not include `access_token` in ordinary debugging output unless you specifically need to inspect it.

---

## Step 3 — Run `from Catalog Sync Schedule`

After the `businesses` rows exist, select:

```text
from Catalog Sync Schedule
```

and execute it once manually.

Expected flow:

```text
Catalog Sync Schedule
        ↓
List Businesses for Catalog Sync
        ↓
Google Sheets
        ↓
Products / FAQ normalization
        ↓
PostgreSQL product + knowledge cache
```

Purpose:

- reads the Google Sheet configured for each business
- loads Products into PostgreSQL
- loads FAQ / knowledge data
- prepares the runtime product search cache
- runs catalog AI enrichment only for new/changed products

### Check that products were synced

```sql
SELECT business_id, COUNT(*) AS product_count
FROM products
GROUP BY business_id
ORDER BY business_id;
```

Do not continue to product-question testing until the relevant business has products in PostgreSQL.

---

## Step 4 — Verify the Meta webhook with `Meta Webhook Verify GET`

Only after:

```text
Database setup ✅
Business row inserted ✅
verify_token saved ✅
```

configure/verify the callback in Meta.

Verification path:

```text
Meta Webhook Verify GET
        ↓
Extract Meta Verify Request
        ↓
Lookup Dynamic Verify Token
        ↓
Build Meta Verify Response
        ↓
Respond Meta Challenge
```

You normally do **not** manually invent the verification query. Meta sends the GET request when you save/verify the webhook callback.

The workflow checks:

```text
hub.mode
hub.verify_token
hub.challenge
```

against `businesses.verify_token`.

If valid:

```text
HTTP 200
hub.challenge
```

If invalid:

```text
HTTP 403
Forbidden
```

Important:

```text
verify_token != access_token
```

- `verify_token` = webhook verification value you choose
- `access_token` = Meta API token used to send messages

Do **not** run Meta verification before the matching `businesses.verify_token` exists in PostgreSQL, otherwise verification will return `403 Forbidden`.

---

## Step 5 — Test `from Meta Webhook POST`

After verification succeeds, test a real customer message.

In production you usually do not manually execute this trigger. Facebook / Instagram / WhatsApp sends POST events automatically.

Incoming flow:

```text
Meta Webhook POST
      ↓
Normalize + Event Filter
      ↓
Dedupe Event
      ↓
Only New Event
      ↓
Load Business + Customer + Conversation
      ↓
Build Base Context
      ↓
AI Enabled Guard
      ↓
Text / Image / Voice processing
      ↓
Intent routing
      ↓
Product / Order / Status / General / Human flow
      ↓
Reply
```

The event filter drops events such as:

```text
Facebook/Instagram message echo
Delivery event
Read event
WhatsApp status event
Unsupported non-message event
```

This prevents the workflow from treating its own outgoing Facebook reply as a new customer message.

### First runtime test

Start with a simple text such as:

```text
এই শাড়ির দাম কত?
```

or a known product name from the synced catalog.

Check that:

```text
businessId
→ correct businesses row
→ correct product catalog
→ correct Page/account token
→ reply goes back from the same Page/account
```

---

## Step 6 — Test `from Follow-up Schedule` last

Do this only after normal messages, product search, and order flow are working.

Select:

```text
from Follow-up Schedule
```

Purpose:

- finds conversations whose follow-up is due
- sends limited follow-up messages
- prevents duplicate follow-ups
- stops after maximum count
- stops when customer opts out
- stops after order confirmation / human handoff where configured

Recommended test order:

```text
1. Facebook/Instagram/WhatsApp normal reply works
2. Product search works
3. Order collection works
4. Order confirmation works
5. Order status works
6. Then test Follow-up Schedule
```

---

# 2. First-time setup summary

Use this exact sequence:

```text
1. from Setup DB Trigger
        ↓
2. Insert / UPSERT businesses rows
        ↓
3. from Catalog Sync Schedule
        ↓
4. Meta Webhook Verify GET
        ↓
5. Meta Webhook POST / real customer message
        ↓
6. from Follow-up Schedule
```

### What runs only once or rarely?

```text
Setup DB Trigger            → first setup / migration
Business UPSERT             → when adding/changing an account
Meta Webhook Verify GET     → when configuring/verifying webhook
```

### What runs automatically after setup?

```text
Meta Webhook POST           → whenever a customer messages
Catalog Sync Schedule       → on schedule
Follow-up Schedule          → on schedule
```

---

# 3. Required `businesses` fields

The workflow expects:

```text
business_id
platform
business_name
verify_token
access_token
reply_url
sheet_document_id
product_sheet_name
faq_sheet_name
order_sheet_name
delivery_charge_default
payment_methods
ai_instructions
active
updated_at
```

`business_id` is the primary key.

Therefore the same `business_id` cannot create duplicate business rows.

The migration includes support for dynamic verification:

```sql
ALTER TABLE businesses
ADD COLUMN IF NOT EXISTS verify_token TEXT;

CREATE INDEX IF NOT EXISTS idx_businesses_verify_token
  ON businesses(verify_token)
  WHERE active = TRUE;
```

---

# 4. Why `ON CONFLICT` must be used

Use UPSERT instead of a plain INSERT:

```text
First run with PAGE_A_ID
→ creates row

Second run with PAGE_A_ID
→ does not create duplicate
→ updates the existing row

Run with PAGE_B_ID
→ creates another business row
```

Recommended reusable pattern:

```sql
INSERT INTO businesses (
  business_id,
  platform,
  business_name,
  verify_token,
  access_token,
  reply_url,
  sheet_document_id,
  product_sheet_name,
  faq_sheet_name,
  order_sheet_name,
  delivery_charge_default,
  payment_methods,
  ai_instructions
)
VALUES (
  'BUSINESS_ID',
  'facebook',
  'Business Name',
  'VERIFY_TOKEN',
  'ACCESS_TOKEN',
  'REPLY_URL',
  'GOOGLE_SHEET_DOCUMENT_ID',
  'Products',
  'FAQ',
  'Orders',
  80,
  'Cash on Delivery',
  'Use only this business product and business information.'
)
ON CONFLICT (business_id)
DO UPDATE SET
  platform = EXCLUDED.platform,
  business_name = EXCLUDED.business_name,
  verify_token = EXCLUDED.verify_token,
  access_token = EXCLUDED.access_token,
  reply_url = EXCLUDED.reply_url,
  sheet_document_id = EXCLUDED.sheet_document_id,
  product_sheet_name = EXCLUDED.product_sheet_name,
  faq_sheet_name = EXCLUDED.faq_sheet_name,
  order_sheet_name = EXCLUDED.order_sheet_name,
  delivery_charge_default = EXCLUDED.delivery_charge_default,
  payment_methods = EXCLUDED.payment_methods,
  ai_instructions = EXCLUDED.ai_instructions,
  updated_at = NOW();
```

---

# 5. Example — 3 Facebook + 3 Instagram + 3 WhatsApp

The following is a single safe UPSERT query with nine example accounts.

All IDs and tokens are placeholders. Never commit real access tokens to GitHub.

```sql
INSERT INTO businesses (
  business_id,
  platform,
  business_name,
  verify_token,
  access_token,
  reply_url,
  sheet_document_id,
  product_sheet_name,
  faq_sheet_name,
  order_sheet_name,
  delivery_charge_default,
  payment_methods,
  ai_instructions
)
VALUES
  -- =========================================================
  -- FACEBOOK PAGES
  -- =========================================================
  (
    'FB_PAGE_ID_RUPLOTA',
    'facebook',
    'Ruplota Facebook',
    'ruplota_fb_verify_2026',
    'FB_PAGE_ACCESS_TOKEN_RUPLOTA',
    'https://graph.facebook.com/v26.0/me/messages',
    'RUPLOTA_GOOGLE_SHEET_ID',
    'Products','FAQ','Orders',
    80,
    'Cash on Delivery',
    'Use only Ruplota Facebook product, price, stock, FAQ and business information. Never guess price.'
  ),
  (
    'FB_PAGE_ID_SAREE_TORONGO',
    'facebook',
    'Saree Torongo Facebook',
    'saree_torongo_fb_verify_2026',
    'FB_PAGE_ACCESS_TOKEN_SAREE_TORONGO',
    'https://graph.facebook.com/v26.0/me/messages',
    'SAREE_TORONGO_GOOGLE_SHEET_ID',
    'Products','FAQ','Orders',
    100,
    'Cash on Delivery',
    'Use only Saree Torongo Facebook data. Never use another business product or price.'
  ),
  (
    'FB_PAGE_ID_KHATI_E_BAZAR',
    'facebook',
    'Khati E Bazar Facebook',
    'khati_e_bazar_fb_verify_2026',
    'FB_PAGE_ACCESS_TOKEN_KHATI_E_BAZAR',
    'https://graph.facebook.com/v26.0/me/messages',
    'KHATI_E_BAZAR_GOOGLE_SHEET_ID',
    'Products','FAQ','Orders',
    120,
    'Cash on Delivery',
    'Use only Khati E Bazar Facebook data.'
  ),

  -- =========================================================
  -- INSTAGRAM ACCOUNTS
  -- =========================================================
  (
    'IG_BUSINESS_ID_RUPLOTA',
    'instagram',
    'Ruplota Instagram',
    'ruplota_ig_verify_2026',
    'IG_ACCESS_TOKEN_RUPLOTA',
    'https://graph.facebook.com/v26.0/me/messages',
    'RUPLOTA_GOOGLE_SHEET_ID',
    'Products','FAQ','Orders',
    80,
    'Cash on Delivery',
    'Use only Ruplota Instagram data.'
  ),
  (
    'IG_BUSINESS_ID_SAREE_TORONGO',
    'instagram',
    'Saree Torongo Instagram',
    'saree_torongo_ig_verify_2026',
    'IG_ACCESS_TOKEN_SAREE_TORONGO',
    'https://graph.facebook.com/v26.0/me/messages',
    'SAREE_TORONGO_GOOGLE_SHEET_ID',
    'Products','FAQ','Orders',
    100,
    'Cash on Delivery',
    'Use only Saree Torongo Instagram data.'
  ),
  (
    'IG_BUSINESS_ID_KHATI_E_BAZAR',
    'instagram',
    'Khati E Bazar Instagram',
    'khati_e_bazar_ig_verify_2026',
    'IG_ACCESS_TOKEN_KHATI_E_BAZAR',
    'https://graph.facebook.com/v26.0/me/messages',
    'KHATI_E_BAZAR_GOOGLE_SHEET_ID',
    'Products','FAQ','Orders',
    120,
    'Cash on Delivery',
    'Use only Khati E Bazar Instagram data.'
  ),

  -- =========================================================
  -- WHATSAPP PHONE NUMBERS
  -- business_id = Meta WhatsApp phone_number_id used by webhook
  -- =========================================================
  (
    'WA_PHONE_NUMBER_ID_RUPLOTA',
    'whatsapp',
    'Ruplota WhatsApp',
    'ruplota_wa_verify_2026',
    'WA_ACCESS_TOKEN_RUPLOTA',
    'https://graph.facebook.com/v26.0/WA_PHONE_NUMBER_ID_RUPLOTA/messages',
    'RUPLOTA_GOOGLE_SHEET_ID',
    'Products','FAQ','Orders',
    80,
    'Cash on Delivery',
    'Use only Ruplota WhatsApp data.'
  ),
  (
    'WA_PHONE_NUMBER_ID_SAREE_TORONGO',
    'whatsapp',
    'Saree Torongo WhatsApp',
    'saree_torongo_wa_verify_2026',
    'WA_ACCESS_TOKEN_SAREE_TORONGO',
    'https://graph.facebook.com/v26.0/WA_PHONE_NUMBER_ID_SAREE_TORONGO/messages',
    'SAREE_TORONGO_GOOGLE_SHEET_ID',
    'Products','FAQ','Orders',
    100,
    'Cash on Delivery',
    'Use only Saree Torongo WhatsApp data.'
  ),
  (
    'WA_PHONE_NUMBER_ID_KHATI_E_BAZAR',
    'whatsapp',
    'Khati E Bazar WhatsApp',
    'khati_e_bazar_wa_verify_2026',
    'WA_ACCESS_TOKEN_KHATI_E_BAZAR',
    'https://graph.facebook.com/v26.0/WA_PHONE_NUMBER_ID_KHATI_E_BAZAR/messages',
    'KHATI_E_BAZAR_GOOGLE_SHEET_ID',
    'Products','FAQ','Orders',
    120,
    'Cash on Delivery',
    'Use only Khati E Bazar WhatsApp data.'
  )

ON CONFLICT (business_id)
DO UPDATE SET
  platform = EXCLUDED.platform,
  business_name = EXCLUDED.business_name,
  verify_token = EXCLUDED.verify_token,
  access_token = EXCLUDED.access_token,
  reply_url = EXCLUDED.reply_url,
  sheet_document_id = EXCLUDED.sheet_document_id,
  product_sheet_name = EXCLUDED.product_sheet_name,
  faq_sheet_name = EXCLUDED.faq_sheet_name,
  order_sheet_name = EXCLUDED.order_sheet_name,
  delivery_charge_default = EXCLUDED.delivery_charge_default,
  payment_methods = EXCLUDED.payment_methods,
  ai_instructions = EXCLUDED.ai_instructions,
  updated_at = NOW();
```

This query is safe to execute repeatedly for the same business IDs.

Expected platform counts for this example:

```text
facebook   3
instagram  3
whatsapp   3
```

Check with:

```sql
SELECT platform, COUNT(*)
FROM businesses
GROUP BY platform
ORDER BY platform;
```

---

# 6. Multiple Meta verify tokens

The verification lookup is dynamic:

```sql
SELECT
  $1::text AS mode,
  $2::text AS challenge,
  $3::text AS verify_token,
  EXISTS (
    SELECT 1
    FROM businesses
    WHERE active = TRUE
      AND COALESCE(verify_token, '') <> ''
      AND verify_token = $3
  ) AS token_valid;
```

Therefore:

```text
Facebook Page A → verify token A
Facebook Page B → verify token B
Facebook Page C → verify token C
```

is supported.

It is also allowed for several rows to share one verify token when they belong to the same Meta App/webhook subscription.

Example:

```text
Ruplota Facebook  → meta_app_1_verify
Ruplota Instagram → meta_app_1_verify
```

The lookup only needs at least one active matching `businesses.verify_token` row.

---

# 7. How business isolation works

## Facebook

```text
Customer messages Facebook Page B
        ↓
incoming recipient/Page identifier
        ↓
businessId = Page B ID
        ↓
businesses.business_id = Page B ID
        ↓
load Page B token + Page B catalog + Page B instructions
        ↓
reply from Page B
```

## Instagram

```text
Customer messages Instagram account
        ↓
receiving Instagram business/account identifier
        ↓
businesses.business_id
        ↓
load only that Instagram row
```

## WhatsApp

The generated workflow normalizes:

```text
metadata.phone_number_id
```

as the WhatsApp `businessId`.

```text
Customer messages WhatsApp Number B
        ↓
metadata.phone_number_id = WA_PHONE_NUMBER_ID_B
        ↓
businesses.business_id = WA_PHONE_NUMBER_ID_B
        ↓
load Number B access token + products + settings
        ↓
reply through Number B endpoint
```

---

# 8. Google Sheet isolation

Every platform row may use a different Sheet:

```text
Facebook Page 1 → Sheet A
Facebook Page 2 → Sheet B
Instagram 1     → Sheet C
WhatsApp 1      → Sheet D
```

Or accounts belonging to the same business may deliberately share one catalog:

```text
Ruplota Facebook  → RUPLOTA_GOOGLE_SHEET_ID
Ruplota Instagram → RUPLOTA_GOOGLE_SHEET_ID
Ruplota WhatsApp  → RUPLOTA_GOOGLE_SHEET_ID
```

Use the same Sheet only when those channels should share the same products, prices, FAQ, and business information.

---

# 9. Update one business later

Run the UPSERT again with the same `business_id`.

Example:

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'FB_PAGE_ID_SAREE_TORONGO',
  'facebook',
  'Saree Torongo Facebook',
  'saree_torongo_fb_verify_2026',
  'NEW_FB_ACCESS_TOKEN',
  'https://graph.facebook.com/v26.0/me/messages',
  'NEW_GOOGLE_SHEET_ID',
  'Products','FAQ','Orders',
  120,
  'Cash on Delivery',
  'Updated instructions for Saree Torongo only.'
)
ON CONFLICT (business_id)
DO UPDATE SET
  platform=EXCLUDED.platform,
  business_name=EXCLUDED.business_name,
  verify_token=EXCLUDED.verify_token,
  access_token=EXCLUDED.access_token,
  reply_url=EXCLUDED.reply_url,
  sheet_document_id=EXCLUDED.sheet_document_id,
  product_sheet_name=EXCLUDED.product_sheet_name,
  faq_sheet_name=EXCLUDED.faq_sheet_name,
  order_sheet_name=EXCLUDED.order_sheet_name,
  delivery_charge_default=EXCLUDED.delivery_charge_default,
  payment_methods=EXCLUDED.payment_methods,
  ai_instructions=EXCLUDED.ai_instructions,
  updated_at=NOW();
```

Only that `business_id` is updated.

---

# 10. Disable without deleting

Disable:

```sql
UPDATE businesses
SET active = FALSE,
    updated_at = NOW()
WHERE business_id = 'FB_PAGE_ID_KHATI_E_BAZAR';
```

Re-enable:

```sql
UPDATE businesses
SET active = TRUE,
    updated_at = NOW()
WHERE business_id = 'FB_PAGE_ID_KHATI_E_BAZAR';
```

This is safer than deleting a configuration while testing.

---

# 11. Troubleshooting by workflow stage

## `Setup DB Trigger` fails

Check the Postgres credential first.

For the local Docker setup, typical values are:

```text
Host: postgres
Port: 5432
Database: n8n_app
```

Use the username/password configured in your `.env`.

## Meta Verify GET returns `403 Forbidden`

Check:

```text
1. businesses row exists
2. active = TRUE
3. verify_token in DB exactly matches Meta Verify Token
4. Setup / Migrate DB was executed first
```

Query:

```sql
SELECT business_id, platform, business_name, verify_token, active
FROM businesses
WHERE verify_token = 'THE_TOKEN_YOU_ENTERED_IN_META';
```

## Catalog Sync returns no products

Check:

```text
sheet_document_id
product_sheet_name
Google Sheets credential
Products tab headers
```

Then:

```sql
SELECT business_id, id, name, price, stock
FROM products
ORDER BY business_id, id;
```

## Customer message arrives but no reply

Inspect these nodes in order:

```text
Normalize + Event Filter
Dedupe Event
Only New Event
Load Business + Customer + Conversation
Build Base Context
AI Enabled Guard
Intent flow
Persist Conversation + Outgoing
Send Platform Reply
```

Most multi-business routing problems can be diagnosed at:

```text
Load Business + Customer + Conversation
```

Confirm that incoming `businessId` exactly matches `businesses.business_id`.

---

# 12. Security rules

Never commit real Meta access tokens to GitHub.

This instruction file intentionally uses placeholders such as:

```text
FB_PAGE_ACCESS_TOKEN_RUPLOTA
IG_ACCESS_TOKEN_RUPLOTA
WA_ACCESS_TOKEN_RUPLOTA
```

Store actual secrets only in your protected runtime configuration/database/credential setup.

Do not print `access_token` in routine debugging SQL.

If an access token is exposed in a screenshot, chat, GitHub commit, or public log, rotate/regenerate it.

---

# 13. Complete first-run checklist

Follow this checklist from top to bottom:

```text
[ ] Import workflow into n8n

[ ] Assign Postgres credentials to Postgres nodes
[ ] Assign Google Sheets credentials
[ ] Assign AI/OpenAI credentials

[ ] Select: from Setup DB Trigger
[ ] Execute Setup / Migrate DB successfully

[ ] Insert / UPSERT businesses row(s)
[ ] Confirm business_id values
[ ] Confirm verify_token values
[ ] Confirm access tokens
[ ] Confirm reply URLs
[ ] Confirm Google Sheet IDs

[ ] Select: from Catalog Sync Schedule
[ ] Execute catalog sync
[ ] Verify products exist in PostgreSQL

[ ] Configure Meta callback
[ ] Verify Meta Webhook Verify GET succeeds

[ ] Send a real customer text message
[ ] Confirm Meta Webhook POST executes
[ ] Confirm correct business row is selected
[ ] Confirm reply comes from the same Page/account/number

[ ] Test repeated product question / response cache
[ ] Test product follow-up: price / image / stock
[ ] Test image input
[ ] Test voice input

[ ] Test CREATE_ORDER
[ ] Test order information collection
[ ] Test order summary
[ ] Test CONFIRM_ORDER
[ ] Test ORDER_STATUS
[ ] Test CANCEL_ORDER

[ ] Finally test Follow-up Schedule
[ ] Test follow-up opt-out / STOP_FOLLOWUP

[ ] Activate/publish workflow for normal production operation
```

---

# 14. Final architecture rule

Always preserve this isolation:

```text
Incoming platform business identifier
        ↓
businesses.business_id
        ↓
exact business configuration
        ↓
correct access token
correct Google Sheet
correct products/prices
correct FAQ
correct AI instructions
correct orders/conversation context
        ↓
reply through that same Page/account/WhatsApp number
```

Never use one business's products, prices, tokens, FAQ, or instructions for another business's customer.
