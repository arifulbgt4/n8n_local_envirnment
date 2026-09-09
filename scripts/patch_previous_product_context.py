import json
from pathlib import Path

p = Path('workflows/modular/05_META_MESSAGING_V4_2.json')
d = json.loads(p.read_text())
n = {x.get('name'): x for x in d.get('nodes', [])}

search = n['Product Search + Response Cache']
sql = search['parameters']['query']
if 'AS previous_product' not in sql:
    needle = '  $3::jsonb AS base,\n'
    if needle not in sql:
        raise SystemExit('Could not find final product-search SELECT base field')
    insert = "  $3::jsonb AS base,\n  (SELECT to_jsonb(pp) FROM products pp WHERE pp.id=(SELECT product_id FROM prev) AND pp.account_id=$1::bigint LIMIT 1) AS previous_product,\n"
    sql = sql.replace(needle, insert, 1)
    search['parameters']['query'] = sql

miss = n['Product Cache MISS']['parameters']['jsCode']
old = "const previous=raw.find(p=>String(p.id)===previousId);\nif(isAlternativeRequest && previous){const pk=logicalKey(previous);products=products.filter(p=>logicalKey(p)!==pk);}"
new = "const previous=raw.find(p=>String(p.id)===previousId)||$json.previous_product||null;\nif(isAlternativeRequest && previous){const pk=logicalKey(previous);products=products.filter(p=>logicalKey(p)!==pk);}"
if old not in miss:
    if '$json.previous_product' not in miss:
        raise SystemExit('Could not find previous-product filter block')
else:
    miss = miss.replace(old, new, 1)
    n['Product Cache MISS']['parameters']['jsCode'] = miss

p.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')) + '\n')

assert 'AS previous_product' in n['Product Search + Response Cache']['parameters']['query']
assert '$json.previous_product' in n['Product Cache MISS']['parameters']['jsCode']
print('previous product context patch validated')
