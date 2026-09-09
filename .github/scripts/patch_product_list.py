import json
from pathlib import Path

p = Path('workflows/modular/05_META_MESSAGING_V4_2.json')
data = json.loads(p.read_text())
nodes = {n.get('name'): n for n in data.get('nodes', [])}

required = [
    'Product Search + Response Cache',
    'Product Cache HIT',
    'Product Cache MISS',
    'Product Answer AI',
    'Parse Product Answer',
    'Merge Draft + Verify Product',
]
missing = [x for x in required if x not in nodes]
if missing:
    raise SystemExit(f'Missing expected nodes: {missing}')

search_node = nodes['Product Search + Response Cache']
sql = search_node['parameters']['query']
old = '  LIMIT 3\n),\ntop_product AS ('
if old not in sql:
    raise SystemExit('Expected Product Search LIMIT 3 block not found')
search_node['parameters']['query'] = sql.replace(old, '  LIMIT 20\n),\ntop_product AS (', 1)

list_regex = r'(?:^|\\b)(?:all products?|product list|products list|catalog|show products?|list products?)(?:\\b|$)|সব\\s*(?:প্রোডাক্ট|পণ্য)|প্রোডাক্ট\\s*লিস্ট|পণ্যের\\s*লিস্ট|কি\\s*কি\\s*(?:প্রোডাক্ট|পণ্য)|কী\\s*কী\\s*(?:প্রোডাক্ট|পণ্য)|সবগুলো\\s*(?:প্রোডাক্ট|পণ্য)|প্রোডাক্টগুলো\\s*(?:দেখাও|দেখান|কি|কী)|পণ্যগুলো\\s*(?:দেখাও|দেখান|কি|কী)'

nodes['Product Cache HIT']['parameters']['jsCode'] = f"""const q=String($json.base?.normalizedQuestion||$json.base?.message||'').toLowerCase();
const isListRequest=/{list_regex}/i.test(q);
if(isListRequest || !$json.cache_reply) return [];
const base=$json.base;
const arr=Array.isArray($json.products)?$json.products:[];
const selected=arr.find(p=>String(p.id)===String($json.top_product_id))||arr[0]||{{}};
let urls=Array.isArray(selected.media_urls)?selected.media_urls:[];
if(!urls.length&&selected.image_url)urls=[selected.image_url];
return [{{json:{{...base,reply:$json.cache_reply,selectedProductId:$json.top_product_id?String($json.top_product_id):'',productImageUrl:urls[0]||'',productImageUrls:urls.slice(0,5),wantsImage:!!base.wantsImage,state:'BROWSING',contextPatch:{{selected_product:{{productId:$json.top_product_id||null}}}},scheduleFollowup:true,cacheId:$json.cache_id}}}}];"""

nodes['Product Cache MISS']['parameters']['jsCode'] = f"""const base=$json.base;
const q=String(base?.normalizedQuestion||base?.message||'').toLowerCase();
const isListRequest=/{list_regex}/i.test(q);
if($json.cache_reply && !isListRequest) return [];
return [{{json:{{...base,products:$json.products||[],topProductId:$json.top_product_id||null,productVersion:$json.product_version||'',isListRequest}}}}];"""

ai = nodes['Product Answer AI']['parameters']
prompt_key = 'text' if isinstance(ai.get('text'), str) else None
if not prompt_key:
    candidates = [(k, v) for k, v in ai.items() if isinstance(v, str) and len(v) > 100]
    if not candidates:
        raise SystemExit('Could not locate Product Answer AI prompt text')
    prompt_key = max(candidates, key=lambda kv: len(kv[1]))[0]
addition = """

PRODUCT LIST RULES:
- `products` is the current active catalog candidate array from PostgreSQL.
- If `isListRequest` is true, do NOT choose one product. List every product supplied in `products` (up to the supplied catalog limit), using each product's verified name, price and stock status when available.
- For a list request, return JSON with `selectedProductId` as an empty string. Never silently fall back to one product.
- For a specific product request, choose only the best verified product and return its id in `selectedProductId`.
- Never invent products that are not present in `products`.
"""
if 'PRODUCT LIST RULES:' not in ai[prompt_key]:
    ai[prompt_key] += addition

nodes['Parse Product Answer']['parameters']['jsCode'] = """const base=$('Product Cache MISS').item.json;
let raw=String($json.text||$json.output||'').trim().replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();
let o;
try{o=JSON.parse(raw)}catch{o={reply:raw||'দুঃখিত, তথ্যটি যাচাই করা যাচ্ছে না।',selectedProductId:''}}
const listRequest=!!base.isListRequest;
const arr=Array.isArray(base.products)?base.products:[];
const requested=String(o.selectedProductId||'');
const selected=listRequest?'':(requested||String(base.topProductId||''));
const product=selected?(arr.find(p=>String(p.id)===selected)||arr[0]||{}):{};
let urls=Array.isArray(product.media_urls)?product.media_urls:[];
if(!urls.length&&product.image_url)urls=[product.image_url];
return [{json:{...base,reply:String(o.reply||''),selectedProductId:selected,productImageUrl:listRequest?'':(urls[0]||''),productImageUrls:listRequest?[]:urls.slice(0,5),wantsImage:listRequest?false:!!base.wantsImage,state:'BROWSING',contextPatch:(!listRequest&&selected)?{selected_product:{productId:selected}}:{},scheduleFollowup:!listRequest&&!!selected,handoff:false}}];"""

merge = nodes['Merge Draft + Verify Product']
merge['parameters'].setdefault('options', {})['queryReplacement'] = "={{ [$json.conversationId,JSON.stringify($json.orderPatch || {}),$json.accountId,$json.orderPatch?.product_query || '',JSON.stringify($json)] }}"

p.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')

# Validate after write.
d = json.loads(p.read_text())
n = {x['name']: x for x in d['nodes']}
assert 'LIMIT 20' in n['Product Search + Response Cache']['parameters']['query']
assert 'isListRequest' in n['Product Cache MISS']['parameters']['jsCode']
assert 'isListRequest' in n['Parse Product Answer']['parameters']['jsCode']
assert "product_query || ''" in n['Merge Draft + Verify Product']['parameters']['options']['queryReplacement']
prompt = ' '.join(str(v) for v in n['Product Answer AI']['parameters'].values())
assert 'PRODUCT LIST RULES:' in prompt
print('workflow patch validated')
