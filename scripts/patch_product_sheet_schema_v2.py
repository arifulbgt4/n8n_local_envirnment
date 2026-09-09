import json
from pathlib import Path

path = Path('workflows/modular/01C_OPERATIONS_INIT_V4_2.json')
data = json.loads(path.read_text())
node = next(n for n in data['nodes'] if n.get('name') == '04.11 - Build Missing Operations Tabs')
code = node['parameters']['jsCode']
start = code.index('const productHeaders=[')
end = code.index('];\nconst headers=', start) + 2
new_block = "const productHeaders=[\n  'Product Name','Category','Subcategory','Price','Currency','Product Description',\n  'Product Image','Image 2','Image 3','Image 4','Image 5','Product URL','Color','Size','SKU',\n  'Stock Status','Stock Qty','Offer','Discount','Aliases','Active','Product ID','Product Group ID',\n  'Variant ID','Variant Name','Updated At'\n];"
node['parameters']['jsCode'] = code[:start] + new_block + code[end:]
path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')

# Validate.
chk = json.loads(path.read_text())
node = next(n for n in chk['nodes'] if n.get('name') == '04.11 - Build Missing Operations Tabs')
for h in ['Product Name','Product Image','Product URL','Color','Size','Stock Status','Product ID','Product Group ID','Variant ID','Variant Name']:
    assert h in node['parameters']['jsCode'], h
print('01C product schema updated')
