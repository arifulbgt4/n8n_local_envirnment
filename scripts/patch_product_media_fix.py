import json
from pathlib import Path

path = Path('workflows/modular/02_CATALOG_SYNC_V4_2.json')
data = json.loads(path.read_text())
node = next(n for n in data['nodes'] if n.get('name') == 'Upsert Product Cache')

node['parameters']['query'] = '''WITH up AS (
INSERT INTO products(
 business_id,account_id,external_product_id,product_group_id,variant_id,sku,name,variant_name,category,subcategory,
 price,currency,stock_qty,stock_status,color,size,description,ai_summary,attributes_json,product_url,image_url,
 offer,discount,aliases,search_text,content_hash,active,updated_at
)
VALUES(
 $1,$2::bigint,$3,$4,$5,$6,$7,$8,$9,$10,
 $11::numeric,$12,$13::int,$14,$15,$16,$17,$18,$19::jsonb,$20,$21,
 $22,$23,$24,$25,$26,$27::boolean,NOW()
)
ON CONFLICT(account_id,external_product_id) DO UPDATE SET
 business_id=EXCLUDED.business_id,product_group_id=EXCLUDED.product_group_id,variant_id=EXCLUDED.variant_id,sku=EXCLUDED.sku,
 name=EXCLUDED.name,variant_name=EXCLUDED.variant_name,category=EXCLUDED.category,subcategory=EXCLUDED.subcategory,
 price=EXCLUDED.price,currency=EXCLUDED.currency,stock_qty=EXCLUDED.stock_qty,stock_status=EXCLUDED.stock_status,
 color=EXCLUDED.color,size=EXCLUDED.size,description=EXCLUDED.description,ai_summary=EXCLUDED.ai_summary,
 attributes_json=EXCLUDED.attributes_json,product_url=EXCLUDED.product_url,image_url=EXCLUDED.image_url,
 offer=EXCLUDED.offer,discount=EXCLUDED.discount,aliases=EXCLUDED.aliases,search_text=EXCLUDED.search_text,
 content_hash=EXCLUDED.content_hash,active=EXCLUDED.active,updated_at=NOW()
RETURNING id
), media_src AS (
 SELECT
   m->>'key' AS media_key,
   COALESCE(NULLIF(m->>'sourceType',''),'url') AS source_type,
   m->>'sourceRef' AS source_ref,
   m->>'resolvedUrl' AS resolved_url,
   COALESCE((m->>'sortOrder')::int,0) AS sort_order
 FROM jsonb_array_elements($28::jsonb) m
 WHERE COALESCE(m->>'resolvedUrl','')<>''
), media_upsert AS (
 INSERT INTO product_media(product_id,media_key,source_type,source_ref,resolved_url,sort_order,active,updated_at)
 SELECT (SELECT id FROM up),s.media_key,s.source_type,s.source_ref,s.resolved_url,s.sort_order,TRUE,NOW()
 FROM media_src s
 ON CONFLICT(product_id,media_key) DO UPDATE SET
   source_type=EXCLUDED.source_type,
   source_ref=EXCLUDED.source_ref,
   resolved_url=EXCLUDED.resolved_url,
   sort_order=EXCLUDED.sort_order,
   active=TRUE,
   updated_at=NOW()
 RETURNING media_key
), media_delete AS (
 DELETE FROM product_media pm
 WHERE pm.product_id=(SELECT id FROM up)
   AND NOT EXISTS (
     SELECT 1 FROM media_src s WHERE s.media_key=pm.media_key
   )
 RETURNING id
)
SELECT (SELECT id FROM up)::text AS product_id,$29::jsonb AS base;'''

path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')

# Validate JSON and the intended reconciliation strategy.
check = json.loads(path.read_text())
q = next(n for n in check['nodes'] if n.get('name') == 'Upsert Product Cache')['parameters']['query']
assert 'ON CONFLICT(product_id,media_key) DO UPDATE SET' in q
assert 'media_delete AS' in q
assert 'NOT EXISTS' in q
assert 'wiped AS' not in q
print('catalog product_media reconciliation patch validated')
