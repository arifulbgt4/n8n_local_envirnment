-- Runs only when the PostgreSQL Docker volume is created for the first time.
-- n8n uses database `n8n`; the AI application uses a separate database `agent_app`.
CREATE DATABASE agent_app;
\connect agent_app
-- AI Customer Support & Order Management V4
-- Application database: agent_app (separate from n8n's own database)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS system_settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS businesses (
  business_id TEXT PRIMARY KEY,
  business_name TEXT NOT NULL,
  delivery_charge_default NUMERIC(12,2) NOT NULL DEFAULT 0,
  payment_methods TEXT NOT NULL DEFAULT 'Cash on Delivery',
  ai_instructions TEXT NOT NULL DEFAULT '',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS business_accounts (
  id BIGSERIAL PRIMARY KEY,
  account_key TEXT NOT NULL UNIQUE,
  business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
  platform TEXT NOT NULL CHECK (platform IN ('facebook','instagram','whatsapp')),
  account_name TEXT,
  external_account_id TEXT NOT NULL,
  meta_app_id TEXT,
  facebook_page_id TEXT,
  instagram_account_id TEXT,
  whatsapp_phone_number_id TEXT,
  whatsapp_business_account_id TEXT,
  meta_app_secret TEXT,
  access_token TEXT,
  verify_token TEXT,
  operations_spreadsheet_id TEXT,
  auto_create_spreadsheet BOOLEAN NOT NULL DEFAULT FALSE,
  graph_api_version TEXT NOT NULL DEFAULT 'v26.0',
  reply_url TEXT,
  conversation_url_template TEXT,
  product_sheet_name TEXT NOT NULL DEFAULT 'Products',
  faq_sheet_name TEXT NOT NULL DEFAULT 'FAQ',
  order_sheet_name TEXT NOT NULL DEFAULT 'Orders',
  human_support_sheet_name TEXT NOT NULL DEFAULT 'HumanSupportQueue',
  ai_provider TEXT NOT NULL DEFAULT 'openai',
  ai_model TEXT NOT NULL DEFAULT 'gpt-5.6-luna',
  ai_prompt_override TEXT NOT NULL DEFAULT '',
  auto_human_on_manual_reply BOOLEAN NOT NULL DEFAULT TRUE,
  max_messages_per_minute INTEGER NOT NULL DEFAULT 8,
  max_ai_turns_per_hour INTEGER NOT NULL DEFAULT 20,
  max_ai_turns_per_day INTEGER NOT NULL DEFAULT 100,
  estimated_tokens_per_turn INTEGER NOT NULL DEFAULT 1800,
  max_estimated_tokens_per_day INTEGER NOT NULL DEFAULT 100000,
  followup_enabled_default BOOLEAN NOT NULL DEFAULT TRUE,
  followup_1_minutes INTEGER NOT NULL DEFAULT 60,
  followup_2_minutes INTEGER NOT NULL DEFAULT 1440,
  control_row_number INTEGER,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(platform, external_account_id)
);
CREATE INDEX IF NOT EXISTS idx_business_accounts_verify_token ON business_accounts(verify_token) WHERE active=TRUE;
CREATE INDEX IF NOT EXISTS idx_business_accounts_business ON business_accounts(business_id) WHERE active=TRUE;

CREATE TABLE IF NOT EXISTS processed_messages (
  id BIGSERIAL PRIMARY KEY,
  platform TEXT NOT NULL,
  external_account_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(platform, external_account_id, message_id)
);

CREATE TABLE IF NOT EXISTS customers (
  id BIGSERIAL PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
  account_id BIGINT NOT NULL REFERENCES business_accounts(id) ON DELETE CASCADE,
  platform TEXT NOT NULL,
  external_user_id TEXT NOT NULL,
  name TEXT,
  phone TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(account_id, external_user_id)
);

CREATE TABLE IF NOT EXISTS conversations (
  id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
  state TEXT NOT NULL DEFAULT 'BROWSING',
  context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  human_mode BOOLEAN NOT NULL DEFAULT FALSE,
  mode_source TEXT,
  handoff_reason TEXT,
  mode_changed_at TIMESTAMPTZ,
  followup_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  followup_count INTEGER NOT NULL DEFAULT 0,
  next_followup_at TIMESTAMPTZ,
  last_customer_at TIMESTAMPTZ,
  last_agent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
  id BIGSERIAL PRIMARY KEY,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound')),
  platform_message_id TEXT,
  message_type TEXT,
  text TEXT,
  media_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_messages_platform_message ON messages(platform_message_id) WHERE platform_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ai_turn_usage (
  id BIGSERIAL PRIMARY KEY,
  business_id TEXT NOT NULL,
  account_id BIGINT NOT NULL,
  customer_id BIGINT NOT NULL,
  conversation_id BIGINT NOT NULL,
  estimated_tokens INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER,
  output_tokens INTEGER,
  total_tokens INTEGER,
  model TEXT,
  purpose TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_turn_usage_customer_time ON ai_turn_usage(account_id, customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_turn_usage_account_day ON ai_turn_usage(account_id, created_at DESC);

CREATE TABLE IF NOT EXISTS bot_outbound_messages (
  id BIGSERIAL PRIMARY KEY,
  platform TEXT NOT NULL,
  external_account_id TEXT NOT NULL,
  customer_external_id TEXT NOT NULL,
  message_id TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bot_outbound_recent ON bot_outbound_messages(external_account_id, created_at DESC);

CREATE TABLE IF NOT EXISTS products (
  id BIGSERIAL PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
  account_id BIGINT NOT NULL REFERENCES business_accounts(id) ON DELETE CASCADE,
  external_product_id TEXT NOT NULL,
  name TEXT NOT NULL,
  category TEXT,
  subcategory TEXT,
  price NUMERIC(12,2),
  currency TEXT NOT NULL DEFAULT 'BDT',
  stock_qty INTEGER,
  stock_status TEXT,
  color TEXT,
  size TEXT,
  description TEXT,
  image_url TEXT,
  offer TEXT,
  discount TEXT,
  aliases TEXT,
  ai_summary TEXT,
  search_text TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(account_id, external_product_id)
);
CREATE INDEX IF NOT EXISTS idx_products_account ON products(account_id);
CREATE INDEX IF NOT EXISTS idx_products_search_trgm ON products USING GIN(search_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS knowledge_base (
  id BIGSERIAL PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
  account_id BIGINT NOT NULL REFERENCES business_accounts(id) ON DELETE CASCADE,
  external_key TEXT NOT NULL,
  question TEXT,
  answer TEXT NOT NULL,
  category TEXT,
  search_text TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(account_id, external_key)
);
CREATE INDEX IF NOT EXISTS idx_kb_account ON knowledge_base(account_id);
CREATE INDEX IF NOT EXISTS idx_kb_search_trgm ON knowledge_base USING GIN(search_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS response_cache (
  id BIGSERIAL PRIMARY KEY,
  business_id TEXT NOT NULL,
  account_id BIGINT NOT NULL,
  intent TEXT NOT NULL,
  normalized_question TEXT NOT NULL,
  product_id BIGINT,
  product_version TEXT NOT NULL DEFAULT '',
  reply TEXT NOT NULL,
  hit_count INTEGER NOT NULL DEFAULT 0,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cache_lookup ON response_cache(account_id,intent,product_id,product_version);
CREATE INDEX IF NOT EXISTS idx_cache_question_trgm ON response_cache USING GIN(normalized_question gin_trgm_ops);

CREATE TABLE IF NOT EXISTS orders (
  id BIGSERIAL PRIMARY KEY,
  order_number TEXT UNIQUE NOT NULL,
  customer_id BIGINT NOT NULL REFERENCES customers(id),
  business_id TEXT NOT NULL REFERENCES businesses(business_id),
  account_id BIGINT NOT NULL REFERENCES business_accounts(id),
  status TEXT NOT NULL DEFAULT 'NEW',
  customer_name TEXT,
  phone TEXT,
  address TEXT,
  area_name TEXT,
  thana TEXT,
  district TEXT,
  payment_method TEXT,
  note TEXT,
  subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,
  delivery_charge NUMERIC(12,2) NOT NULL DEFAULT 0,
  total NUMERIC(12,2) NOT NULL DEFAULT 0,
  confirmed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_orders_account_created ON orders(account_id, created_at DESC);

CREATE TABLE IF NOT EXISTS order_items (
  id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id BIGINT REFERENCES products(id),
  sku TEXT,
  product_name TEXT NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
  total NUMERIC(12,2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS human_handoffs (
  id BIGSERIAL PRIMARY KEY,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  customer_id BIGINT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  business_id TEXT NOT NULL,
  account_id BIGINT NOT NULL,
  reason TEXT,
  source TEXT,
  summary TEXT,
  status TEXT NOT NULL DEFAULT 'PENDING',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_handoff_pending ON human_handoffs(account_id,conversation_id,status);

CREATE TABLE IF NOT EXISTS followup_log (
  id BIGSERIAL PRIMARY KEY,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  followup_no INTEGER NOT NULL,
  message TEXT NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(conversation_id, followup_no)
);

-- V4.2 product variant/media reconciliation migration
ALTER TABLE products ADD COLUMN IF NOT EXISTS product_group_id TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS variant_id TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS variant_name TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS sku TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS product_url TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS attributes_json JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_products_group ON products(account_id, product_group_id) WHERE active=TRUE;
CREATE INDEX IF NOT EXISTS idx_products_variant ON products(account_id, variant_id) WHERE active=TRUE;

CREATE TABLE IF NOT EXISTS product_media (
  id BIGSERIAL PRIMARY KEY,
  product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  media_key TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'url',
  source_ref TEXT,
  resolved_url TEXT NOT NULL,
  cache_key TEXT,
  content_hash TEXT,
  local_path TEXT,
  mime_type TEXT,
  file_size BIGINT,
  facebook_attachment_id TEXT,
  instagram_attachment_id TEXT,
  cached_at TIMESTAMPTZ,
  attachment_updated_at TIMESTAMPTZ,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(product_id, media_key)
);
CREATE INDEX IF NOT EXISTS idx_product_media_product ON product_media(product_id, sort_order) WHERE active=TRUE;

-- Persistent local/Meta product media cache
ALTER TABLE product_media ADD COLUMN IF NOT EXISTS cache_key TEXT;
ALTER TABLE product_media ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE product_media ADD COLUMN IF NOT EXISTS local_path TEXT;
ALTER TABLE product_media ADD COLUMN IF NOT EXISTS mime_type TEXT;
ALTER TABLE product_media ADD COLUMN IF NOT EXISTS file_size BIGINT;
ALTER TABLE product_media ADD COLUMN IF NOT EXISTS facebook_attachment_id TEXT;
ALTER TABLE product_media ADD COLUMN IF NOT EXISTS instagram_attachment_id TEXT;
ALTER TABLE product_media ADD COLUMN IF NOT EXISTS cached_at TIMESTAMPTZ;
ALTER TABLE product_media ADD COLUMN IF NOT EXISTS attachment_updated_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_product_media_facebook_attachment ON product_media(facebook_attachment_id) WHERE facebook_attachment_id IS NOT NULL;

CREATE OR REPLACE FUNCTION invalidate_product_media_cache_on_source_change()
RETURNS trigger AS $$
BEGIN
  IF NEW.resolved_url IS DISTINCT FROM OLD.resolved_url
     OR NEW.source_ref IS DISTINCT FROM OLD.source_ref THEN
    NEW.cache_key := NULL;
    NEW.content_hash := NULL;
    NEW.local_path := NULL;
    NEW.mime_type := NULL;
    NEW.file_size := NULL;
    NEW.facebook_attachment_id := NULL;
    NEW.instagram_attachment_id := NULL;
    NEW.cached_at := NULL;
    NEW.attachment_updated_at := NULL;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_product_media_cache_invalidate ON product_media;
CREATE TRIGGER trg_product_media_cache_invalidate
BEFORE UPDATE OF source_ref,resolved_url ON product_media
FOR EACH ROW EXECUTE FUNCTION invalidate_product_media_cache_on_source_change();


DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='order_items_product_id_fkey'
      AND conrelid='order_items'::regclass
  ) THEN
    ALTER TABLE order_items DROP CONSTRAINT order_items_product_id_fkey;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='order_items_product_id_fkey'
      AND conrelid='order_items'::regclass
  ) THEN
    ALTER TABLE order_items
      ADD CONSTRAINT order_items_product_id_fkey
      FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL;
  END IF;
END $$;
