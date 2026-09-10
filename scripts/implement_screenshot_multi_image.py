import json
import re
from pathlib import Path
from uuid import uuid4

ROOT = Path('.')
MSG = ROOT / 'workflows/modular/05_META_MESSAGING_V4_2.json'
CAT = ROOT / 'workflows/modular/02_CATALOG_SYNC_V4_2.json'
OPS = ROOT / 'workflows/modular/01C_OPERATIONS_INIT_V4_2.json'
GS = ROOT / 'integrations/google-apps-script/PRODUCT_IMAGE_SYNC.gs'
DOC = ROOT / 'docs/PRODUCT_CATALOG.md'


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')


def nodes_by_name(wf):
    return {n['name']: n for n in wf['nodes']}


def set_main(connections, source, targets):
    connections[source] = {'main': [[{'node': t, 'type': 'main', 'index': 0} for t in targets]]}


def product_headers_10():
    return [
        'Product ID','Product Name','Category','Subcategory','Price','Currency','Stock Qty','Stock Status','Color','Size','SKU','Product Description',
        'Product Image', *[f'Image {i}' for i in range(2, 11)],
        'Product URL','Offer','Discount','Aliases','Active','Product Group ID','Variant ID','Variant Name','Updated At',
        *[f'Resolved Image {i}' for i in range(1, 11)],
        *[f'_Image File ID {i}' for i in range(1, 11)],
        *[f'_Image Hash {i}' for i in range(1, 11)],
    ]


# ---------------------------------------------------------------------------
# 05 Meta Messaging: screenshot/product-image analysis + sequential multi-image
# ---------------------------------------------------------------------------
msg = load_json(MSG)
mn = nodes_by_name(msg)
required = [
    'Attach Image Analysis','Quick Intent Router','Product Search + Response Cache',
    'Only Product Image Request','Load Product Media Send Cache','Flatten Product Media Send Cache',
    'Route Facebook Product Image Cache','Route Other Product Image','Persist Facebook Product Image Cache',
    'Store Product Image Bot Message ID'
]
missing = [x for x in required if x not in mn]
if missing:
    raise RuntimeError(f'Missing expected messaging nodes: {missing}')

mn['Attach Image Analysis']['parameters']['jsCode'] = r"""const base = $('Only Image Binary').item.json;
const raw = String($json.text || $json.content || $json.output || $json.response || '').trim();
if (!raw) throw new Error('Image analysis returned an empty result.');
const caption = String(base.message || '').trim();
const stop = new Set(['the','a','an','this','that','is','are','of','with','and','or','to','for','in','on','from','visible','image','photo','picture','screenshot','looks','appears','product','item','shown','দেখা','যাচ্ছে','এই','এটা','একটি','ছবি','পণ্য','প্রোডাক্ট']);
const compact = [...new Set(raw.toLowerCase().replace(/[^\p{L}\p{N}._-]+/gu,' ').split(/\s+/).filter(x => x.length > 1 && !stop.has(x)))].slice(0, 55).join(' ');
const searchQuery = [caption, compact || raw].filter(Boolean).join(' ').replace(/\s+/g,' ').trim().slice(0, 900);
const enrichedMessage = [caption, `[IMAGE ANALYSIS: ${raw}]`].filter(Boolean).join('\n');
return [{json:{
  ...base,
  mediaAnalysis: raw,
  imageSearchQuery: searchQuery,
  productSearchQuery: searchQuery,
  imageProductLookup: true,
  message: enrichedMessage,
  normalizedQuestion: searchQuery.toLowerCase()
}}];"""

quick = mn['Quick Intent Router']['parameters']['jsCode']
# Expand the image vocabulary used to decide whether images should be sent.
quick = re.sub(
    r"const wantsImage=.*?;\\?\n?const productQuestion=",
    "const wantsImage=has('ছবি','ছবিটা','ছবিগুলো','আরও ছবি','আরো ছবি','কয়েকটা ছবি','কয়েকটা ছবি','অনেক ছবি','ফটো','পিক','পিকটা','পিকগুলো','image','images','more image','more images','multiple images','couple images','couple of images','few images','photo','photos','pic','pics','picture','pictures','chobi','chhobi','chobita','pic dao','pic daw','pic den','photo daw','photo dao');\\nconst productQuestion=",
    quick,
    count=1,
    flags=re.S,
)
if "imageProductLookup" not in quick:
    quick = quick.replace(
        "let intent='',needsAI=false;",
        "let intent='',needsAI=false;\nif(j.imageProductLookup===true || (j.messageType==='image' && String(j.mediaAnalysis||'').trim())) intent='PRODUCT_SEARCH';"
    )
    # Turn the first top-level `if(has(` following our inserted forced intent into `else if`.
    marker = "if(j.imageProductLookup===true || (j.messageType==='image' && String(j.mediaAnalysis||'').trim())) intent='PRODUCT_SEARCH';"
    idx = quick.find(marker)
    if idx >= 0:
        pos = quick.find("if(has(", idx + len(marker))
        if pos >= 0:
            quick = quick[:pos] + "else " + quick[pos:]
mn['Quick Intent Router']['parameters']['jsCode'] = quick

# For screenshot lookups, use the compact image-derived query for product ranking.
search_node = mn['Product Search + Response Cache']
qr = search_node['parameters'].get('options', {}).get('queryReplacement', '')
if '$json.productSearchQuery' not in qr:
    qr = qr.replace(
        "[$json.accountId,$json.normalizedQuestion,JSON.stringify($json),JSON.stringify($json.context || {})]",
        "[$json.accountId,($json.productSearchQuery||$json.normalizedQuestion),JSON.stringify($json),JSON.stringify($json.context || {})]"
    )
search_node['parameters'].setdefault('options', {})['queryReplacement'] = qr

mn['Only Product Image Request']['parameters']['jsCode'] = r"""const out=[];
const digitMap={'০':'0','১':'1','২':'2','৩':'3','৪':'4','৫':'5','৬':'6','৭':'7','৮':'8','৯':'9'};
const imageRe=/ছবি|ফটো|পিক|image|images|photo|photos|pic|pics|picture|pictures|chobi|chhobi/i;
const multiRe=/আরও|আরো|more|another|extra|কয়েক|কয়েক|অনেক|multiple|several|few|couple|different\s+angle|other\s+angle/i;
const allRe=/(?:সব\s*গুলো|সবগুলো|সব|সকল|all|every)\s*(?:টা|টি|গুলো)?\s*(?:ছবি|পিক|ফটো|image|images|pic|pics|photo|photos|picture|pictures)|(?:ছবিগুলো|পিকগুলো|ফটোগুলো|all\s+images|all\s+photos|all\s+pics)/i;
const words=[
  [/\b(?:one)\b|একটা|একটি/i,1],[/\b(?:two|couple)\b|দুইটা|দুইটি|দুটো|দুটি/i,2],
  [/\bthree\b|তিনটা|তিনটি|তিনটে/i,3],[/\bfour\b|চারটা|চারটি/i,4],
  [/\bfive\b|পাঁচটা|পাঁচটি/i,5],[/\bsix\b|ছয়টা|ছয়টা|ছয়টি|ছয়টি/i,6],
  [/\bseven\b|সাতটা|সাতটি/i,7],[/\beight\b|আটটা|আটটি/i,8],
  [/\bnine\b|নয়টা|নয়টা|নয়টি|নয়টি/i,9],[/\bten\b|দশটা|দশটি/i,10]
];
for(const item of $input.all()){
  const j=item.json||{};
  const txt=String(j.normalizedQuestion||j.message||'').toLowerCase().replace(/\s+/g,' ').trim();
  const inferred=imageRe.test(txt);
  if(!j.wantsImage&&!inferred) continue;

  const previousProductId=String(j.context?.selected_product?.productId||'');
  const currentProductId=String(j.selectedProductId||j.contextPatch?.selected_product?.productId||'');
  const additionalRequest=inferred&&multiRe.test(txt);
  const selectedProductId=(additionalRequest&&previousProductId)?previousProductId:(currentProductId||previousProductId);

  let normalizedDigits=txt.replace(/[০-৯]/g,d=>digitMap[d]||d);
  let requested=1;
  const numeric=normalizedDigits.match(/(?:^|\s)(10|[1-9])\s*(?:টা|টি|টি করে|x)?\s*(?:ছবি|পিক|ফটো|image|images|pic|pics|photo|photos|picture|pictures)/i)
    || normalizedDigits.match(/(?:ছবি|পিক|ফটো|image|images|pic|pics|photo|photos|picture|pictures)\s*(?:এর|of)?\s*(10|[1-9])/i);
  if(numeric) requested=Number(numeric[1]);
  else {
    for(const [re,n] of words){if(re.test(txt)&&imageRe.test(txt)){requested=n;break;}}
    if(allRe.test(txt)) requested=10;
    else if(requested===1 && /couple/i.test(txt)) requested=2;
    else if(requested===1 && /কয়েক|কয়েক|multiple|several|few|অনেক/i.test(txt)) requested=4;
    else if(requested===1 && /আরও|আরো|more|another|extra|different\s+angle|other\s+angle/i.test(txt)) requested=3;
  }
  requested=Math.max(1,Math.min(10,requested));

  const colorMap=[
    ['লাল','red'],['red','red'],['নীল','blue'],['blue','blue'],['সবুজ','green'],['green','green'],
    ['কালো','black'],['black','black'],['সাদা','white'],['white','white'],['হলুদ','yellow'],['yellow','yellow'],
    ['গোলাপি','pink'],['pink','pink'],['মেরুন','maroon'],['maroon','maroon'],['বেগুনি','purple'],['purple','purple'],
    ['কমলা','orange'],['orange','orange'],['ধূসর','gray'],['grey','gray'],['gray','gray'],['বাদামি','brown'],['brown','brown']
  ];
  let requestedColor='';
  for(const [needle,canon] of colorMap){if(txt.includes(needle)){requestedColor=canon;break;}}

  let urls=Array.isArray(j.productImageUrls)?j.productImageUrls.filter(Boolean):[];
  if(!urls.length&&j.productImageUrl) urls=[j.productImageUrl];
  urls=[...new Set(urls.map(String))].slice(0,10);
  const preferredUrl=urls[0]||'';

  if(selectedProductId||preferredUrl){
    out.push({json:{...j,selectedProductId,productImageUrl:preferredUrl,requestedImageCount:requested,wantsAllImages:requested>1,requestedColor,additionalImageRequest:additionalRequest}});
  }
}
return out;"""

mn['Load Product Media Send Cache']['parameters']['query'] = r"""WITH input AS (
  SELECT $4::jsonb AS base
), params AS (
  SELECT NULLIF($1,'')::bigint AS product_id,
         GREATEST(1,LEAST(COALESCE(NULLIF($2,'')::int,1),10)) AS requested_count,
         NULLIF($3,'')::text AS preferred_url
), ranked AS (
  SELECT pm.*,
         ROW_NUMBER() OVER (
           ORDER BY CASE WHEN p.preferred_url IS NOT NULL AND pm.resolved_url=p.preferred_url THEN 0 ELSE 1 END,
                    pm.sort_order,pm.id
         ) AS rn
  FROM product_media pm
  CROSS JOIN params p
  WHERE p.product_id IS NOT NULL
    AND pm.product_id=p.product_id
    AND pm.active=TRUE
    AND COALESCE(pm.resolved_url,'')<>''
), selected AS (
  SELECT r.* FROM ranked r CROSS JOIN params p WHERE r.rn<=p.requested_count
), fallback AS (
  SELECT NULL::bigint AS id,'direct-image'::text AS media_key,
         p.preferred_url AS resolved_url,''::text AS cache_key,''::text AS local_path,
         ''::text AS mime_type,0::bigint AS file_size,''::text AS facebook_attachment_id,
         1::bigint AS rn
  FROM params p
  WHERE p.preferred_url IS NOT NULL AND NOT EXISTS(SELECT 1 FROM selected)
), media AS (
  SELECT id,media_key,resolved_url,COALESCE(cache_key,'') AS cache_key,
         COALESCE(local_path,'') AS local_path,COALESCE(mime_type,'') AS mime_type,
         COALESCE(file_size,0) AS file_size,COALESCE(facebook_attachment_id,'') AS facebook_attachment_id,rn
  FROM selected
  UNION ALL
  SELECT * FROM fallback
)
SELECT input.base,media.id::text AS media_row_id,media.media_key,media.resolved_url,
       media.cache_key,media.local_path,media.mime_type,media.file_size::text AS file_size,
       media.facebook_attachment_id,media.rn::int AS media_index
FROM input CROSS JOIN media
ORDER BY media.rn;"""
mn['Load Product Media Send Cache']['parameters'].setdefault('options', {})['queryReplacement'] = "={{ [$json.selectedProductId,String($json.requestedImageCount||1),$json.productImageUrl,JSON.stringify($json)] }}"

mn['Flatten Product Media Send Cache']['parameters']['jsCode'] = r"""const b=$json.base||{};
const resolved=String($json.resolved_url||b.productImageUrl||'').trim();
if(!resolved)return[];
const mediaIndex=Number($json.media_index||1);
const mediaKey=String($json.media_key||`image-${mediaIndex}`);
const cacheKey=String($json.cache_key||`acct-${b.accountId}-prod-${b.selectedProductId||'direct'}-${mediaKey}`);
return [{json:{...b,mediaRowId:String($json.media_row_id||''),mediaIndex,mediaKey,resolvedUrl:resolved,productImageUrl:resolved,cacheKey,localPath:String($json.local_path||''),mimeType:String($json.mime_type||''),fileSize:Number($json.file_size||0),facebookAttachmentId:String($json.facebook_attachment_id||'')}}];"""

# Store non-Facebook product-image message IDs against the current flattened media item.
store = mn['Store Product Image Bot Message ID']
store['parameters']['options']['queryReplacement'] = "={{ [$('Flatten Product Media Send Cache').item.json.platform,$('Flatten Product Media Send Cache').item.json.externalAccountId,$('Flatten Product Media Send Cache').item.json.senderId,String($json.message_id || $json.messageId || '')] }}"

# Explicit one-at-a-time loop prevents a multi-item batch from collapsing into one Messenger image send.
loop_name = 'Loop Product Images Sequentially'
if loop_name not in mn:
    loop = {
        'parameters': {'batchSize': 1, 'options': {}},
        'id': str(uuid4()),
        'name': loop_name,
        'type': 'n8n-nodes-base.splitInBatches',
        'typeVersion': 3,
        'position': [5620, -20],
    }
    msg['nodes'].append(loop)
    mn[loop_name] = loop

c = msg['connections']
set_main(c, 'Flatten Product Media Send Cache', [loop_name])
# SplitInBatches v3: output 0 = Done, output 1 = Loop.
c[loop_name] = {'main': [[], [
    {'node':'Route Facebook Product Image Cache','type':'main','index':0},
    {'node':'Route Other Product Image','type':'main','index':0},
]]}
set_main(c, 'Persist Facebook Product Image Cache', [loop_name])
set_main(c, 'Store Product Image Bot Message ID', [loop_name])

save_json(MSG, msg)


# ---------------------------------------------------------------------------
# Catalog: keep up to 10 images for each product in product_media.
# ---------------------------------------------------------------------------
cat = load_json(CAT)
cn = nodes_by_name(cat)
npr = cn['Normalize Product Row']['parameters']['jsCode']
old_source = "const sourceImages=['Product Image','Image 2','Image 3','Image 4','Image 5'].map(k=>val(k, k==='Product Image'?'Image':'', k==='Product Image'?'Photo':'', k==='Product Image'?'ছবি':''));"
new_source = "const sourceImages=['Product Image',...Array.from({length:9},(_,i)=>`Image ${i+2}`)].map(k=>val(k, k==='Product Image'?'Image':'', k==='Product Image'?'Photo':'', k==='Product Image'?'ছবি':''));"
old_res = "const resolvedImages=['Resolved Image 1','Resolved Image 2','Resolved Image 3','Resolved Image 4','Resolved Image 5'].map(k=>val(k));"
new_res = "const resolvedImages=Array.from({length:10},(_,i)=>val(`Resolved Image ${i+1}`));"
if old_source not in npr or old_res not in npr:
    raise RuntimeError('Could not locate 5-image catalog normalization code')
npr = npr.replace(old_source, new_source).replace(old_res, new_res)
cn['Normalize Product Row']['parameters']['jsCode'] = npr
save_json(CAT, cat)


# ---------------------------------------------------------------------------
# Operations spreadsheet: new/DB-restored Products tabs expose 10 image slots.
# ---------------------------------------------------------------------------
ops = load_json(OPS)
on = nodes_by_name(ops)
headers = product_headers_10()
headers_js = json.dumps(headers, ensure_ascii=False, separators=(',', ':'))
for node_name in ['04.11 - Build Missing Operations Tabs','04.19 - Build Database to Sheet Payload']:
    code = on[node_name]['parameters']['jsCode']
    code2, count = re.subn(r"const productHeaders=\[.*?\];", f"const productHeaders={headers_js};", code, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f'Could not replace productHeaders in {node_name}')
    on[node_name]['parameters']['jsCode'] = code2

payload = on['04.19 - Build Database to Sheet Payload']['parameters']['jsCode']
payload = payload.replace("const imgs=[0,1,2,3,4].map(i=>m[i]||'');", "const imgs=Array.from({length:10},(_,i)=>m[i]||'');")
payload = payload.replace("...imgs,'','','','','','','','','',''", "...imgs,...Array(20).fill('')")
on['04.19 - Build Database to Sheet Payload']['parameters']['jsCode'] = payload

# Do not truncate future image columns during DB restore / empty-DB seed import.
for n in ops['nodes']:
    p = n.get('parameters', {})
    for k, v in list(p.items()):
        if isinstance(v, str):
            p[k] = v.replace('Products!A:AO', 'Products!A:ZZ')

save_json(OPS, ops)


# ---------------------------------------------------------------------------
# Apps Script: resolve direct/in-cell/over-grid images for slots 1..10.
# ---------------------------------------------------------------------------
gs = GS.read_text(encoding='utf-8')
gs = gs.replace("const SCRIPT_VERSION = '4.2-products-v5-grid-borders';", "const SCRIPT_VERSION = '4.2-products-v6-ten-images';")
for i in range(6, 11):
    marker = "  'Image 5',\n  'Product URL',"
    if marker in gs:
        extra = ''.join(f"  'Image {j}',\n" for j in range(6, 11))
        gs = gs.replace(marker, "  'Image 5',\n" + extra + "  'Product URL',", 1)
        break

gs = re.sub(r"const IMAGE_HEADERS = \[.*?\];", "const IMAGE_HEADERS = ['Product Image', " + ', '.join(repr(f'Image {i}') for i in range(2,11)) + "];", gs, count=1)
gs = re.sub(r"const RESOLVED_HEADERS = \[.*?\];", "const RESOLVED_HEADERS = [" + ', '.join(repr(f'Resolved Image {i}') for i in range(1,11)) + "];", gs, count=1)
gs = re.sub(r"const FILE_ID_HEADERS = \[.*?\];", "const FILE_ID_HEADERS = [" + ', '.join(repr(f'_Image File ID {i}') for i in range(1,11)) + "];", gs, count=1)
gs = re.sub(r"const HASH_HEADERS = \[.*?\];", "const HASH_HEADERS = [" + ', '.join(repr(f'_Image Hash {i}') for i in range(1,11)) + "];", gs, count=1)
# Add aliases for image columns 6..10 so existing custom headers normalize correctly.
alias_anchor = "  'Image 5': ['Image 5', 'Product Image 5', 'Photo 5', 'Picture 5'],\n"
if alias_anchor in gs and "'Image 10':" not in gs:
    extra_alias = ''.join(f"  'Image {i}': ['Image {i}', 'Product Image {i}', 'Photo {i}', 'Picture {i}'],\n" for i in range(6,11))
    gs = gs.replace(alias_anchor, alias_anchor + extra_alias, 1)
GS.write_text(gs, encoding='utf-8')


# ---------------------------------------------------------------------------
# Documentation.
# ---------------------------------------------------------------------------
doc = DOC.read_text(encoding='utf-8')
doc = doc.replace('`Product Image` and `Image 2..5`', '`Product Image` and `Image 2..10`')
doc = doc.replace('`Resolved Image 1..5`', '`Resolved Image 1..10`')
if 'multiple Messenger images' not in doc.lower():
    doc += """

## Screenshot lookup and multiple Messenger images

When a customer sends a product screenshot/photo, the messaging workflow sends the binary image to the account's `IMAGE_PRODUCT_ANALYSIS` AI configuration, builds a compact product-search query from the analysis, and forces the result through the product-search path. The normal product answer therefore uses the matched PostgreSQL catalog rather than treating the screenshot as a generic message.

A product can keep up to 10 ordered media rows (`Product Image`, `Image 2..10`). Requests such as “more images”, “couple of images”, “3 pictures”, “কয়েকটা ছবি”, or “সবগুলো ছবি” resolve against the currently selected product. The workflow loads the requested number of active `product_media` rows (maximum 10) and sends them to Messenger one at a time through an explicit `SplitInBatches` loop. This avoids collapsing a multi-image request into a single outgoing image and preserves the existing Facebook attachment cache for every image.
"""
DOC.write_text(doc, encoding='utf-8')


# ---------------------------------------------------------------------------
# Static validation.
# ---------------------------------------------------------------------------
for path in [MSG, CAT, OPS]:
    wf = load_json(path)
    names = {n['name'] for n in wf['nodes']}
    for source, groups in wf.get('connections', {}).items():
        if source not in names:
            raise RuntimeError(f'{path}: connection source missing: {source}')
        for outputs in groups.values():
            if not isinstance(outputs, list):
                continue
            for output in outputs:
                if not isinstance(output, list):
                    continue
                for edge in output:
                    if edge.get('node') not in names:
                        raise RuntimeError(f"{path}: missing connection target {edge.get('node')} from {source}")

msg_check = load_json(MSG)
check_nodes = nodes_by_name(msg_check)
if 'requestedImageCount' not in check_nodes['Only Product Image Request']['parameters']['jsCode']:
    raise RuntimeError('Requested image count logic missing')
if 'LIMIT 1' in check_nodes['Load Product Media Send Cache']['parameters']['query'].upper():
    raise RuntimeError('Product media query still limits every request to one image')
if 'Loop Product Images Sequentially' not in check_nodes:
    raise RuntimeError('Sequential product image loop missing')
if 'productSearchQuery' not in check_nodes['Attach Image Analysis']['parameters']['jsCode']:
    raise RuntimeError('Screenshot product-search enrichment missing')
if 'Image 10' not in nodes_by_name(load_json(CAT))['Normalize Product Row']['parameters']['jsCode']:
    # Source list is dynamically generated, so inspect for length 9 instead.
    if 'length:9' not in nodes_by_name(load_json(CAT))['Normalize Product Row']['parameters']['jsCode']:
        raise RuntimeError('Catalog does not support 10 image slots')
if "'Image 10'" not in GS.read_text(encoding='utf-8'):
    raise RuntimeError('Apps Script does not expose Image 10')

print('Screenshot analysis + sequential multi-image feature migration completed')
