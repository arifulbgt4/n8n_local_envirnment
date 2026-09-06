CREATE TABLE IF NOT EXISTS processed_messages (
  id BIGSERIAL PRIMARY KEY,
  platform TEXT NOT NULL,
  message_id TEXT NOT NULL,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (platform, message_id)
);

CREATE TABLE IF NOT EXISTS customers (
  id BIGSERIAL PRIMARY KEY,
  platform TEXT NOT NULL,
  external_user_id TEXT NOT NULL,
  business_id TEXT,
  display_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (platform, external_user_id)
);

CREATE TABLE IF NOT EXISTS conversations (
  id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  state TEXT NOT NULL DEFAULT 'BROWSING',
  context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
  id BIGSERIAL PRIMARY KEY,
  order_number TEXT UNIQUE,
  customer_id BIGINT REFERENCES customers(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'PENDING',
  phone TEXT,
  address TEXT,
  subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,
  total NUMERIC(12,2) NOT NULL DEFAULT 0,
  google_sheet_synced BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  confirmed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS order_items (
  id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  sku TEXT,
  product_name TEXT,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
  total NUMERIC(12,2) NOT NULL CHECK (total >= 0)
);

CREATE INDEX IF NOT EXISTS idx_processed_messages_message_id
  ON processed_messages(message_id);

CREATE INDEX IF NOT EXISTS idx_customers_platform_external_user
  ON customers(platform, external_user_id);

CREATE INDEX IF NOT EXISTS idx_conversations_customer_id
  ON conversations(customer_id);

CREATE INDEX IF NOT EXISTS idx_orders_customer_id
  ON orders(customer_id);
