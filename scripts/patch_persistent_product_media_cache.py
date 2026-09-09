import json
from pathlib import Path

ROOT = Path('.')

MIGRATION_SQL = r'''

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
'''

MEDIA_COLUMNS = '''  cache_key TEXT,\n  content_hash TEXT,\n  local_path TEXT,\n  mime_type TEXT,\n  file_size BIGINT,\n  facebook_attachment_id TEXT,\n  instagram_attachment_id TEXT,\n  cached_at TIMESTAMPTZ,\n  attachment_updated_at TIMESTAMPTZ,\n'''


def patch_compose():
    p = ROOT / 'docker-compose.yml'
    text = p.read_text(encoding='utf-8')
    if '\n  media-cache:\n' not in text:
        block = '''\n  media-cache:\n    build:\n      context: ./services/media-cache\n    container_name: n8n-media-cache\n    restart: unless-stopped\n    environment:\n      PORT: 3001\n      CACHE_DIR: /data/product-media\n      MAX_IMAGE_BYTES: ${PRODUCT_MEDIA_CACHE_MAX_BYTES:-26214400}\n      GRAPH_VERSION: v26.0\n      TZ: ${TZ}\n    ports:\n      - "127.0.0.1:3001:3001"\n    volumes:\n      - product_media_cache:/data/product-media\n    healthcheck:\n      test: ["CMD", "node", "-e", "fetch('http://127.0.0.1:3001/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]\n      interval: 10s\n      timeout: 5s\n      retries: 10\n\n'''
        text = text.replace('\n  n8n:\n', block + '  n8n:\n')
    if '      media-cache:\n        condition: service_healthy\n' not in text:
        text = text.replace(
            '    depends_on:\n      postgres:\n        condition: service_healthy\n',
            '    depends_on:\n      postgres:\n        condition: service_healthy\n      media-cache:\n        condition: service_healthy\n'
        )
    if '  product_media_cache:\n' not in text:
        text = text.rstrip() + '\n  product_media_cache:\n    name: n8n_product_media_cache\n'
    p.write_text(text, encoding='utf-8')

    envp = ROOT / '.env.example'
    if envp.exists():
        env = envp.read_text(encoding='utf-8')
        if 'PRODUCT_MEDIA_CACHE_MAX_BYTES=' not in env:
            env = env.rstrip() + '\n\n# Persistent local product image cache (25 MiB per image by default)\nPRODUCT_MEDIA_CACHE_MAX_BYTES=26214400\n'
            envp.write_text(env, encoding='utf-8')


def patch_sql_file(rel):
    p = ROOT / rel
    if not p.exists():
        return
    text = p.read_text(encoding='utf-8')
    if 'facebook_attachment_id TEXT' not in text:
        text = text.replace(
            '  resolved_url TEXT NOT NULL,\n  sort_order INTEGER NOT NULL DEFAULT 0,',
            '  resolved_url TEXT NOT NULL,\n' + MEDIA_COLUMNS + '  sort_order INTEGER NOT NULL DEFAULT 0,'
        )
    if 'invalidate_product_media_cache_on_source_change' not in text:
        marker = 'CREATE INDEX IF NOT EXISTS idx_product_media_product ON product_media(product_id, sort_order) WHERE active=TRUE;'
        if marker in text:
            text = text.replace(marker, marker + MIGRATION_SQL)
        else:
            text = text.rstrip() + MIGRATION_SQL + '\n'
    p.write_text(text, encoding='utf-8')


def save_json(path, data, compact=False):
    if compact:
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def upsert_node(data, node):
    for i, current in enumerate(data.get('nodes', [])):
        if current.get('name') == node['name']:
            data['nodes'][i] = node
            return
    data.setdefault('nodes', []).append(node)


def patch_setup_workflow():
    p = ROOT / 'workflows/modular/01_SETUP_CONFIG_V4_2.json'
    data = json.loads(p.read_text(encoding='utf-8'))
    node = next((n for n in data.get('nodes', []) if 'Apply / Migrate Database Schema' in n.get('name', '')), None)
    if not node:
        raise RuntimeError('Setup migration node not found')
    query = node.setdefault('parameters', {}).get('query', '')
    if 'facebook_attachment_id' not in query:
        node['parameters']['query'] = query.rstrip() + MIGRATION_SQL
    save_json(p, data)


def patch_catalog_workflow():
    p = ROOT / 'workflows/modular/02_CATALOG_SYNC_V4_2.json'
    data = json.loads(p.read_text(encoding='utf-8'))

    expand = {
        'parameters': {
            'jsCode': "const out=[];for(const item of $input.all()){const j=item.json||{};const b=j.base||{};const media=Array.isArray(b.media)?b.media:[];for(const m of media){const url=String(m?.resolvedUrl||'').trim();if(!url)continue;const mediaKey=String(m?.key||`image-${Number(m?.sortOrder||1)}`);out.push({json:{productId:String(j.product_id||''),accountId:String(b.accountId||''),mediaKey,sourceUrl:url,cacheKey:`acct-${b.accountId}-prod-${j.product_id}-${mediaKey}`}});}}return out;"
        },
        'type': 'n8n-nodes-base.code', 'typeVersion': 2,
        'position': [-400, 1260], 'id': 'd6f47db5-4146-4650-b4e4-10425570e74a',
        'name': 'Expand Product Media Cache Warmup'
    }
    warm = {
        'parameters': {
            'method': 'POST', 'url': 'http://media-cache:3001/v1/cache',
            'sendBody': True, 'contentType': 'raw', 'rawContentType': 'application/json',
            'body': "={{ JSON.stringify({sourceUrl:$json.sourceUrl,cacheKey:$json.cacheKey}) }}",
            'options': {'timeout': 20000}
        },
        'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2,
        'position': [-160, 1260], 'id': '095ddb06-3d3d-45c4-bb05-01c1431c5817',
        'name': 'Warm Local Product Media Cache', 'continueOnFail': True
    }
    upsert_node(data, expand)
    upsert_node(data, warm)

    con = data.setdefault('connections', {})
    spec = con.setdefault('Upsert Product Cache', {'main': [[]]})
    spec.setdefault('main', [[]])
    if not spec['main']:
        spec['main'] = [[]]
    edge = {'node': 'Expand Product Media Cache Warmup', 'type': 'main', 'index': 0}
    if edge not in spec['main'][0]:
        spec['main'][0].append(edge)
    con['Expand Product Media Cache Warmup'] = {'main': [[{'node': 'Warm Local Product Media Cache', 'type': 'main', 'index': 0}]]}
    save_json(p, data, compact=True)


def patch_meta_workflow():
    p = ROOT / 'workflows/modular/05_META_MESSAGING_V4_2.json'
    data = json.loads(p.read_text(encoding='utf-8'))

    only = next((n for n in data.get('nodes', []) if n.get('name') == 'Only Product Image Request'), None)
    if not only:
        raise RuntimeError('Only Product Image Request node not found')
    only['parameters']['jsCode'] = "const out=[];for(const item of $input.all()){const j=item.json||{};if(!j.wantsImage)continue;let urls=Array.isArray(j.productImageUrls)?j.productImageUrls.filter(Boolean):[];if(!urls.length&&j.productImageUrl)urls=[j.productImageUrl];urls=[...new Set(urls)].slice(0,5);urls.forEach((url,i)=>out.push({json:{...j,productImageUrl:String(url),mediaSortOrder:i+1}}));}return out;"

    nodes = [
        {
            'parameters': {
                'operation': 'executeQuery',
                'query': "WITH input AS (SELECT $4::jsonb AS base), pm AS (SELECT * FROM product_media WHERE product_id=NULLIF($1,'')::bigint AND active=TRUE AND (sort_order=$2::int OR resolved_url=$3) ORDER BY CASE WHEN resolved_url=$3 THEN 0 ELSE 1 END,sort_order LIMIT 1) SELECT input.base,pm.id::text AS media_row_id,pm.media_key,pm.resolved_url,COALESCE(pm.cache_key,'') AS cache_key,COALESCE(pm.local_path,'') AS local_path,COALESCE(pm.mime_type,'') AS mime_type,COALESCE(pm.file_size,0)::text AS file_size,COALESCE(pm.facebook_attachment_id,'') AS facebook_attachment_id FROM input LEFT JOIN pm ON TRUE;",
                'options': {'queryReplacement': "={{ [$json.selectedProductId,$json.mediaSortOrder,$json.productImageUrl,JSON.stringify($json)] }}"}
            },
            'type': 'n8n-nodes-base.postgres', 'typeVersion': 2.6,
            'position': [5200, -40], 'id': '21f7a5cb-9fa9-453e-884e-35006be024fd', 'name': 'Load Product Media Send Cache'
        },
        {
            'parameters': {
                'jsCode': "const b=$json.base||{};const mediaKey=String($json.media_key||`image-${Number(b.mediaSortOrder||1)}`);const cacheKey=String($json.cache_key||`acct-${b.accountId}-prod-${b.selectedProductId}-${mediaKey}`);return [{json:{...b,mediaRowId:String($json.media_row_id||''),mediaKey,resolvedUrl:String($json.resolved_url||b.productImageUrl||''),cacheKey,localPath:String($json.local_path||''),mimeType:String($json.mime_type||''),fileSize:Number($json.file_size||0),facebookAttachmentId:String($json.facebook_attachment_id||'')}}];"
            },
            'type': 'n8n-nodes-base.code', 'typeVersion': 2,
            'position': [5440, -40], 'id': '9b089f90-3c84-4315-938b-b683b6722f99', 'name': 'Flatten Product Media Send Cache'
        },
        {
            'parameters': {'jsCode': "return $input.all().filter(i=>String(i.json.platform||'').toLowerCase()==='facebook');"},
            'type': 'n8n-nodes-base.code', 'typeVersion': 2,
            'position': [5680, -120], 'id': 'ac3d3a8a-10b1-4c3b-93af-d06ef5b96ea0', 'name': 'Route Facebook Product Image Cache'
        },
        {
            'parameters': {'jsCode': "return $input.all().filter(i=>String(i.json.platform||'').toLowerCase()!=='facebook');"},
            'type': 'n8n-nodes-base.code', 'typeVersion': 2,
            'position': [5680, 80], 'id': '8a12a054-c344-457e-86b9-76e854c8a256', 'name': 'Route Other Product Image'
        },
        {
            'parameters': {
                'method': 'POST', 'url': 'http://media-cache:3001/v1/facebook/send-image',
                'sendBody': True, 'contentType': 'raw', 'rawContentType': 'application/json',
                'body': "={{ JSON.stringify({accessToken:$json.accessToken,recipientId:$json.senderId,sourceUrl:$json.resolvedUrl||$json.productImageUrl,cacheKey:$json.cacheKey,attachmentId:$json.facebookAttachmentId||'',localPath:$json.localPath||'',mimeType:$json.mimeType||'',fileSize:$json.fileSize||0,graphVersion:'v26.0'}) }}",
                'options': {'timeout': 30000}
            },
            'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2,
            'position': [5920, -120], 'id': 'b524e76e-8021-44d0-b875-1fc584f8a19a', 'name': 'Send Facebook Product Image Cached'
        },
        {
            'parameters': {
                'operation': 'executeQuery',
                'query': "WITH upd AS (UPDATE product_media SET cache_key=COALESCE(NULLIF($2,''),cache_key),local_path=COALESCE(NULLIF($3,''),local_path),mime_type=COALESCE(NULLIF($4,''),mime_type),file_size=CASE WHEN $5::bigint>0 THEN $5::bigint ELSE file_size END,facebook_attachment_id=COALESCE(NULLIF($6,''),facebook_attachment_id),cached_at=CASE WHEN COALESCE(NULLIF($3,''),local_path) IS NOT NULL THEN NOW() ELSE cached_at END,attachment_updated_at=CASE WHEN NULLIF($6,'') IS NOT NULL THEN NOW() ELSE attachment_updated_at END,updated_at=NOW() WHERE id=NULLIF($1,'')::bigint RETURNING id), bot AS (INSERT INTO bot_outbound_messages(platform,external_account_id,customer_external_id,message_id) SELECT 'facebook',$7,$8,$9 WHERE COALESCE($9,'')<>'' ON CONFLICT(message_id) DO NOTHING RETURNING id) SELECT $9::text AS message_id,EXISTS(SELECT 1 FROM upd) AS media_cache_saved,EXISTS(SELECT 1 FROM bot) AS bot_message_saved;",
                'options': {'queryReplacement': "={{ [$('Flatten Product Media Send Cache').item.json.mediaRowId,$json.cacheKey||$('Flatten Product Media Send Cache').item.json.cacheKey,$json.localPath||$('Flatten Product Media Send Cache').item.json.localPath,$json.mimeType||$('Flatten Product Media Send Cache').item.json.mimeType,$json.fileSize||$('Flatten Product Media Send Cache').item.json.fileSize,$json.attachmentId||'',$('Flatten Product Media Send Cache').item.json.externalAccountId,$('Flatten Product Media Send Cache').item.json.senderId,$json.messageId||''] }}"}
            },
            'type': 'n8n-nodes-base.postgres', 'typeVersion': 2.6,
            'position': [6160, -120], 'id': '22d1e361-a903-460a-8217-b44907a54b08', 'name': 'Persist Facebook Product Image Cache'
        }
    ]
    for node in nodes:
        upsert_node(data, node)

    obsolete = {'Route Meta Product Image', 'Route WhatsApp Product Image', 'Download Product Image Binary', 'Send Meta Product Image Binary'}
    data['nodes'] = [n for n in data['nodes'] if n.get('name') not in obsolete]
    con = data.setdefault('connections', {})
    for name in list(con):
        if name in obsolete:
            con.pop(name, None)
    for spec in con.values():
        for outputs in spec.get('main', []):
            outputs[:] = [e for e in outputs if e.get('node') not in obsolete]

    con['Only Product Image Request'] = {'main': [[{'node': 'Load Product Media Send Cache', 'type': 'main', 'index': 0}]]}
    con['Load Product Media Send Cache'] = {'main': [[{'node': 'Flatten Product Media Send Cache', 'type': 'main', 'index': 0}]]}
    con['Flatten Product Media Send Cache'] = {'main': [[
        {'node': 'Route Facebook Product Image Cache', 'type': 'main', 'index': 0},
        {'node': 'Route Other Product Image', 'type': 'main', 'index': 0}
    ]]}
    con['Route Facebook Product Image Cache'] = {'main': [[{'node': 'Send Facebook Product Image Cached', 'type': 'main', 'index': 0}]]}
    con['Send Facebook Product Image Cached'] = {'main': [[{'node': 'Persist Facebook Product Image Cache', 'type': 'main', 'index': 0}]]}
    con['Route Other Product Image'] = {'main': [[{'node': 'Send Verified Product Image', 'type': 'main', 'index': 0}]]}
    save_json(p, data)


def patch_docs():
    p = ROOT / 'docs/PRODUCT_CATALOG.md'
    if not p.exists():
        return
    text = p.read_text(encoding='utf-8')
    if '## Persistent local product media cache' not in text:
        text += '''\n\n## Persistent local product media cache\n\nProduct images are pre-warmed by catalog sync into the Docker named volume `n8n_product_media_cache` through the internal `media-cache` service. Image bytes therefore survive normal `docker compose down` / `up` cycles as long as volumes are not deleted.\n\nFor Facebook, the first successful send creates a reusable Meta `attachment_id`, stored in `product_media.facebook_attachment_id`. Later requests use that attachment ID directly, avoiding Google Drive downloads and repeated binary uploads. If Meta rejects the cached ID, the service falls back to the persistent local file/source URL, uploads a fresh reusable attachment, sends it, and returns the new ID for PostgreSQL persistence.\n\nDo not run `docker compose down -v` during normal restarts; that deletes the persistent product media cache volume.\n'''
        p.write_text(text, encoding='utf-8')


def validate_workflow(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    names = {n.get('name') for n in data.get('nodes', [])}
    for src, spec in data.get('connections', {}).items():
        if src not in names:
            raise RuntimeError(f'{path}: missing connection source {src}')
        for outputs in spec.get('main', []):
            for e in outputs:
                if e.get('node') not in names:
                    raise RuntimeError(f'{path}: missing connection target {e.get("node")}')


patch_compose()
for rel in ['init-db/001-init.sql', 'docs/DATABASE_SCHEMA.sql', 'docs/RESET_APPLICATION_DATABASE.sql']:
    patch_sql_file(rel)
patch_setup_workflow()
patch_catalog_workflow()
patch_meta_workflow()
patch_docs()

for rel in [
    'workflows/modular/01_SETUP_CONFIG_V4_2.json',
    'workflows/modular/02_CATALOG_SYNC_V4_2.json',
    'workflows/modular/05_META_MESSAGING_V4_2.json',
]:
    validate_workflow(ROOT / rel)

print('Persistent product media cache patch applied successfully')
