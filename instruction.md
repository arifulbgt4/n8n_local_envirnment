# Multi-Platform `businesses` Configuration Guide

This file explains how to configure multiple Facebook Pages, Instagram accounts, and WhatsApp Cloud API numbers for the n8n AI Customer Support & Order Management workflow.

The system is designed so that each incoming message is matched to the correct `businesses` row by `business_id`. That row then determines which access token, Google Sheet, product catalog, FAQ, delivery settings, AI instructions, and reply endpoint are used.

The same `businesses` table is reused for every platform. You do **not** create a new table for every Facebook Page, Instagram account, or WhatsApp number.

---

## 1. Required `businesses` table fields

The workflow expects these fields:

```sql
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

`business_id` is the primary key, so the same business ID cannot create duplicate rows.

The database migration should include:

```sql
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS verify_token TEXT;

CREATE INDEX IF NOT EXISTS idx_businesses_verify_token
  ON businesses(verify_token)
  WHERE active = TRUE;
```

---

## 2. Why `ON CONFLICT` is important

Use `INSERT ... ON CONFLICT (business_id) DO UPDATE` instead of a plain `INSERT`.

Behavior:

```text
First execution with PAGE_A_ID
→ new row created

Second execution with PAGE_A_ID
→ no duplicate row
→ existing row updated

Execution with PAGE_B_ID
→ another new row created
```

This makes the setup node safe to run repeatedly.

---

## 3. Recommended reusable UPSERT format

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

# 4. Facebook examples — 3 Pages

Replace every placeholder with your real Page ID, Page access token, verify token, and Google Sheet document ID.

## Facebook Page 1 — Ruplota

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'FB_PAGE_ID_RUPLOTA',
  'facebook',
  'Ruplota',
  'ruplota_verify_2026',
  'FB_PAGE_ACCESS_TOKEN_RUPLOTA',
  'https://graph.facebook.com/v26.0/me/messages',
  'RUPLOTA_GOOGLE_SHEET_ID',
  'Products',
  'FAQ',
  'Orders',
  80,
  'Cash on Delivery',
  'Use only Ruplota product, price, stock, FAQ and business information. Never guess product price.'
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

## Facebook Page 2 — Saree Torongo

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'FB_PAGE_ID_SAREE_TORONGO',
  'facebook',
  'Saree Torongo',
  'saree_torongo_verify_2026',
  'FB_PAGE_ACCESS_TOKEN_SAREE_TORONGO',
  'https://graph.facebook.com/v26.0/me/messages',
  'SAREE_TORONGO_GOOGLE_SHEET_ID',
  'Products',
  'FAQ',
  'Orders',
  100,
  'Cash on Delivery',
  'Use only Saree Torongo product, price, stock, FAQ and business information. Never use another Page data.'
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

## Facebook Page 3 — Khati E Bazar

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'FB_PAGE_ID_KHATI_E_BAZAR',
  'facebook',
  'Khati E Bazar',
  'khati_e_bazar_verify_2026',
  'FB_PAGE_ACCESS_TOKEN_KHATI_E_BAZAR',
  'https://graph.facebook.com/v26.0/me/messages',
  'KHATI_E_BAZAR_GOOGLE_SHEET_ID',
  'Products',
  'FAQ',
  'Orders',
  120,
  'Cash on Delivery',
  'Use only Khati E Bazar product, price, stock, FAQ and business information.'
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

---

# 5. Instagram examples — 3 accounts

For the current workflow design, Instagram rows use `platform = 'instagram'` and their own business/account identifier and access token.

## Instagram Account 1

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'IG_BUSINESS_ID_RUPLOTA',
  'instagram',
  'Ruplota Instagram',
  'ruplota_instagram_verify_2026',
  'IG_ACCESS_TOKEN_RUPLOTA',
  'https://graph.facebook.com/v26.0/me/messages',
  'RUPLOTA_INSTAGRAM_GOOGLE_SHEET_ID',
  'Products',
  'FAQ',
  'Orders',
  80,
  'Cash on Delivery',
  'Use only Ruplota Instagram catalog and business information.'
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

## Instagram Account 2

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'IG_BUSINESS_ID_SAREE_TORONGO',
  'instagram',
  'Saree Torongo Instagram',
  'saree_torongo_instagram_verify_2026',
  'IG_ACCESS_TOKEN_SAREE_TORONGO',
  'https://graph.facebook.com/v26.0/me/messages',
  'SAREE_TORONGO_INSTAGRAM_GOOGLE_SHEET_ID',
  'Products',
  'FAQ',
  'Orders',
  100,
  'Cash on Delivery',
  'Use only Saree Torongo Instagram catalog and business information.'
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

## Instagram Account 3

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'IG_BUSINESS_ID_KHATI_E_BAZAR',
  'instagram',
  'Khati E Bazar Instagram',
  'khati_e_bazar_instagram_verify_2026',
  'IG_ACCESS_TOKEN_KHATI_E_BAZAR',
  'https://graph.facebook.com/v26.0/me/messages',
  'KHATI_E_BAZAR_INSTAGRAM_GOOGLE_SHEET_ID',
  'Products',
  'FAQ',
  'Orders',
  120,
  'Cash on Delivery',
  'Use only Khati E Bazar Instagram catalog and business information.'
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

---

# 6. WhatsApp examples — 3 phone numbers

For WhatsApp Cloud API, `business_id` should match the identifier your webhook normalization uses for the receiving WhatsApp business number. In the generated workflow this is the `phone_number_id` from Meta webhook metadata.

The reply URL therefore includes that phone number ID.

## WhatsApp Number 1

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'WA_PHONE_NUMBER_ID_RUPLOTA',
  'whatsapp',
  'Ruplota WhatsApp',
  'ruplota_whatsapp_verify_2026',
  'WA_ACCESS_TOKEN_RUPLOTA',
  'https://graph.facebook.com/v26.0/WA_PHONE_NUMBER_ID_RUPLOTA/messages',
  'RUPLOTA_WHATSAPP_GOOGLE_SHEET_ID',
  'Products',
  'FAQ',
  'Orders',
  80,
  'Cash on Delivery',
  'Use only Ruplota WhatsApp catalog and business information.'
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

## WhatsApp Number 2

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'WA_PHONE_NUMBER_ID_SAREE_TORONGO',
  'whatsapp',
  'Saree Torongo WhatsApp',
  'saree_torongo_whatsapp_verify_2026',
  'WA_ACCESS_TOKEN_SAREE_TORONGO',
  'https://graph.facebook.com/v26.0/WA_PHONE_NUMBER_ID_SAREE_TORONGO/messages',
  'SAREE_TORONGO_WHATSAPP_GOOGLE_SHEET_ID',
  'Products',
  'FAQ',
  'Orders',
  100,
  'Cash on Delivery',
  'Use only Saree Torongo WhatsApp catalog and business information.'
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

## WhatsApp Number 3

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'WA_PHONE_NUMBER_ID_KHATI_E_BAZAR',
  'whatsapp',
  'Khati E Bazar WhatsApp',
  'khati_e_bazar_whatsapp_verify_2026',
  'WA_ACCESS_TOKEN_KHATI_E_BAZAR',
  'https://graph.facebook.com/v26.0/WA_PHONE_NUMBER_ID_KHATI_E_BAZAR/messages',
  'KHATI_E_BAZAR_WHATSAPP_GOOGLE_SHEET_ID',
  'Products',
  'FAQ',
  'Orders',
  120,
  'Cash on Delivery',
  'Use only Khati E Bazar WhatsApp catalog and business information.'
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

---

# 7. Insert many businesses in one query

You can also configure many businesses in one SQL statement.

Example with 3 Facebook Pages, 3 Instagram accounts, and 3 WhatsApp numbers:

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
  -- Facebook
  ('FB_PAGE_1','facebook','Facebook Shop 1','fb_verify_1','FB_TOKEN_1','https://graph.facebook.com/v26.0/me/messages','FB_SHEET_1','Products','FAQ','Orders',80,'Cash on Delivery','Use only Facebook Shop 1 data.'),
  ('FB_PAGE_2','facebook','Facebook Shop 2','fb_verify_2','FB_TOKEN_2','https://graph.facebook.com/v26.0/me/messages','FB_SHEET_2','Products','FAQ','Orders',100,'Cash on Delivery','Use only Facebook Shop 2 data.'),
  ('FB_PAGE_3','facebook','Facebook Shop 3','fb_verify_3','FB_TOKEN_3','https://graph.facebook.com/v26.0/me/messages','FB_SHEET_3','Products','FAQ','Orders',120,'Cash on Delivery','Use only Facebook Shop 3 data.'),

  -- Instagram
  ('IG_ACCOUNT_1','instagram','Instagram Shop 1','ig_verify_1','IG_TOKEN_1','https://graph.facebook.com/v26.0/me/messages','IG_SHEET_1','Products','FAQ','Orders',80,'Cash on Delivery','Use only Instagram Shop 1 data.'),
  ('IG_ACCOUNT_2','instagram','Instagram Shop 2','ig_verify_2','IG_TOKEN_2','https://graph.facebook.com/v26.0/me/messages','IG_SHEET_2','Products','FAQ','Orders',100,'Cash on Delivery','Use only Instagram Shop 2 data.'),
  ('IG_ACCOUNT_3','instagram','Instagram Shop 3','ig_verify_3','IG_TOKEN_3','https://graph.facebook.com/v26.0/me/messages','IG_SHEET_3','Products','FAQ','Orders',120,'Cash on Delivery','Use only Instagram Shop 3 data.'),

  -- WhatsApp
  ('WA_PHONE_NUMBER_ID_1','whatsapp','WhatsApp Shop 1','wa_verify_1','WA_TOKEN_1','https://graph.facebook.com/v26.0/WA_PHONE_NUMBER_ID_1/messages','WA_SHEET_1','Products','FAQ','Orders',80,'Cash on Delivery','Use only WhatsApp Shop 1 data.'),
  ('WA_PHONE_NUMBER_ID_2','whatsapp','WhatsApp Shop 2','wa_verify_2','WA_TOKEN_2','https://graph.facebook.com/v26.0/WA_PHONE_NUMBER_ID_2/messages','WA_SHEET_2','Products','FAQ','Orders',100,'Cash on Delivery','Use only WhatsApp Shop 2 data.'),
  ('WA_PHONE_NUMBER_ID_3','whatsapp','WhatsApp Shop 3','wa_verify_3','WA_TOKEN_3','https://graph.facebook.com/v26.0/WA_PHONE_NUMBER_ID_3/messages','WA_SHEET_3','Products','FAQ','Orders',120,'Cash on Delivery','Use only WhatsApp Shop 3 data.')

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

This is safe to execute repeatedly because every row is protected by the `business_id` primary key and `ON CONFLICT (business_id) DO UPDATE`.

---

# 8. Dynamic Meta webhook verification

The n8n verification flow should be:

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

The lookup checks `businesses.verify_token`:

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

If:

```text
hub.mode = subscribe
AND
hub.verify_token exists in businesses.verify_token
```

then return:

```text
hub.challenge
HTTP 200
```

Otherwise return:

```text
Forbidden
HTTP 403
```

### Important verify-token note

A Meta verify token is a value you choose for webhook verification; it is not the same thing as the Page access token.

```text
verify_token  → webhook verification only
access_token  → sending API requests/replies
```

The database design allows each business row to have a different verify token.

It also allows multiple rows to share the same verify token. That is useful when multiple Pages/accounts are subscribed through the same Meta App/webhook configuration.

---

# 9. How incoming messages are isolated by business

## Facebook

The workflow normalizes the receiving Page identifier as `businessId`.

Example:

```text
Customer sends message to Facebook Page B
        ↓
Webhook recipient/Page ID = FB_PAGE_2
        ↓
businesses.business_id = FB_PAGE_2
        ↓
load Facebook Shop 2 configuration
        ↓
use FB_TOKEN_2 + FB_SHEET_2 + Shop 2 products
        ↓
reply through Facebook Shop 2
```

## Instagram

```text
Customer sends Instagram message
        ↓
Instagram receiving business/account ID
        ↓
match businesses.business_id
        ↓
load only that Instagram configuration
```

## WhatsApp

```text
Customer sends WhatsApp message
        ↓
metadata.phone_number_id
        ↓
businesses.business_id = phone_number_id
        ↓
load matching WhatsApp token + sheet + product catalog
        ↓
reply through that phone_number_id
```

---

# 10. Verify inserted rows

After inserting/updating configuration, run:

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

Do **not** include `access_token` in ordinary debugging output unless you actually need to inspect it.

Count rows by platform:

```sql
SELECT platform, COUNT(*)
FROM businesses
GROUP BY platform
ORDER BY platform;
```

With the 9-row example above, expected result:

```text
facebook   3
instagram  3
whatsapp   3
```

---

# 11. Update only one Page/account later

Because the setup uses UPSERT, you can safely run only that business row again.

Example:

```sql
INSERT INTO businesses (
  business_id, platform, business_name, verify_token, access_token,
  reply_url, sheet_document_id, product_sheet_name, faq_sheet_name,
  order_sheet_name, delivery_charge_default, payment_methods, ai_instructions
)
VALUES (
  'FB_PAGE_2',
  'facebook',
  'Facebook Shop 2',
  'fb_verify_2',
  'NEW_FB_TOKEN_2',
  'https://graph.facebook.com/v26.0/me/messages',
  'NEW_FB_SHEET_2',
  'Products',
  'FAQ',
  'Orders',
  120,
  'Cash on Delivery',
  'Updated instructions for Facebook Shop 2 only.'
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

Only `FB_PAGE_2` is updated. Other Facebook, Instagram, and WhatsApp rows remain unchanged.

---

# 12. Disable a business without deleting it

```sql
UPDATE businesses
SET active = FALSE,
    updated_at = NOW()
WHERE business_id = 'FB_PAGE_3';
```

Re-enable:

```sql
UPDATE businesses
SET active = TRUE,
    updated_at = NOW()
WHERE business_id = 'FB_PAGE_3';
```

This is safer than deleting configuration during testing.

---

# 13. Google Sheet isolation

Each row can point to a different Google Sheet:

```text
Facebook Page 1  → Sheet A
Facebook Page 2  → Sheet B
Instagram 1      → Sheet C
WhatsApp 1       → Sheet D
```

Or multiple platform accounts belonging to the same business can intentionally share one sheet:

```text
Ruplota Facebook  → RUPLOTA_SHEET_ID
Ruplota Instagram → RUPLOTA_SHEET_ID
Ruplota WhatsApp  → RUPLOTA_SHEET_ID
```

The correct choice depends on whether those platform accounts should share the same product catalog and business information.

---

# 14. Security rules

Never commit real access tokens into GitHub.

This `instruction.md` intentionally uses placeholders such as:

```text
FB_TOKEN_1
IG_TOKEN_1
WA_TOKEN_1
```

Real secrets should be inserted only into your secured runtime/database/credential setup.

Also avoid printing `access_token` in normal SQL debug queries.

---

# 15. Quick checklist

Before testing a platform account:

```text
[ ] Setup/Migration SQL executed
[ ] businesses row inserted
[ ] business_id matches incoming webhook identifier
[ ] platform value is correct
[ ] verify_token configured
[ ] access_token configured
[ ] reply_url configured
[ ] Google Sheet ID configured
[ ] Products tab exists
[ ] FAQ tab exists if FAQ sync is enabled
[ ] Orders tab exists if order sync is enabled
[ ] Catalog Sync has populated PostgreSQL products
[ ] Webhook verification succeeds
[ ] Test customer message is received
[ ] Reply is sent from the same Page/account/WhatsApp number
```

---

## Final rule

The central rule is:

```text
Incoming business identifier
        ↓
businesses.business_id
        ↓
exact platform/business configuration
        ↓
only that business's token, product data, prices, FAQ, orders, and AI instructions
```

Never mix one business's product or price data with another business's customer conversation.
