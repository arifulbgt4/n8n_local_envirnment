import json
from pathlib import Path

ROOT = Path('.')


def load(path):
    return json.loads(path.read_text())


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n')

# 1) Keep newly-created Products sheets merchant-friendly.
init_path = ROOT / 'workflows/modular/01C_OPERATIONS_INIT_V4_2.json'
init = load(init_path)
for n in init['nodes']:
    if n.get('name') == '04.11 - Build Missing Operations Tabs':
        n['parameters']['jsCode'] = r'''const ctx=$('04.09 - Normalize Spreadsheet Init Context').item.json;
const productHeaders=[
  'Product Name','Price','Product Description','Product Image','Stock Status','Stock Qty',
  'Category','Subcategory','Color','Size','SKU','Product URL','Offer','Discount','Aliases','Active','Updated At'
];
const headers={
  "Products":productHeaders,
  "FAQ":["FAQ ID","Question","Answer","Category","Active","Updated At"],
  "Orders":["Order Number","Created At","Status","Customer Name","Phone","Address","Product","Quantity","Unit Price","Delivery Charge","Grand Total","Payment Method","Notes","Conversation ID"],
  "HumanSupportQueue":["Conversation ID","Business ID","Business Name","Platform","Account ID","Customer ID","Customer External ID","Latest Customer Message","Latest Message Time","Conversation URL","Mode","Handoff Reason","Handoff Source","Status","Updated At"],
  "HumanSupportLatest":["Conversation ID","Business ID","Business Name","Platform","Account ID","Customer ID","Customer External ID","Latest Customer Message","Latest Message Time","Conversation URL","Mode","Handoff Reason","Handoff Source","Status","Updated At"],
  "_System":["Key","Value","Updated At"]
};
const existing=new Set(($json.sheets||[]).map(s=>s.properties?.title));
const missing=Object.keys(headers).filter(t=>!existing.has(t));
const data=missing.map(t=>({range:`${t}!A1`,majorDimension:'ROWS',values:[headers[t]]}));
if(missing.includes('HumanSupportLatest'))data.push({range:'HumanSupportLatest!A2',majorDimension:'ROWS',values:[[ '=SORT(FILTER(HumanSupportQueue!A2:O,HumanSupportQueue!A2:A<>""),15,FALSE)' ]]});
if(missing.includes('_System'))data.push({range:'_System!A2',majorDimension:'ROWS',values:[['schema_version','4.2',new Date().toISOString()],['account_key',ctx.account_key,new Date().toISOString()]]});
return[{json:{...ctx,missing,requests:missing.map(title=>({addSheet:{properties:{title}}})),headerData:data}}];'''
        break
else:
    raise RuntimeError('01C header node not found')
save(init_path, init)

# 2) Stop rewriting an existing merchant Products sheet. Normalize in memory only.
cat_path = ROOT / 'workflows/modular/02_CATALOG_SYNC_V4_2.json'
cat = load(cat_path)
for n in cat['nodes']:
    if n.get('name') == '05M.06 - Normalize + Categorize Legacy Products':
        code = n['parameters']['jsCode']
        code = code.replace('legacyDetected:!ctx.targetSheetExists,', 'legacyDetected:false,')
        code = code.replace('legacyDetected:migrationNeeded,', 'legacyDetected:false,')
        n['parameters']['jsCode'] = code
    elif n.get('name') == 'Normalize Product Row':
        code = n['parameters']['jsCode']
        replacements = {
            "val('Product Name','Name','Product')": "val('Product Name','Name','Product','Item Name','Title','পণ্যের নাম','প্রোডাক্ট নাম','নাম')",
            "val('Product Description','Description')": "val('Product Description','Description','Details','Product Details','বিবরণ','ডিটেইলস')",
            "val('Price','Price (৳)','Price(৳)','মূল্য')": "val('Price','Price (৳)','Price(৳)','Price Tk','Price BDT','Sale Price','Selling Price','Rate','Amount','মূল্য','দাম')",
            "val('Stock Qty','Quantity','Qty')": "val('Stock Qty','Stock Quantity','Quantity','Qty','Inventory','Available Qty','পরিমাণ','স্টক পরিমাণ')",
            "val('Stock Status','Stock')": "val('Stock Status','Stock','Availability','Available','Inventory Status','স্টক','স্ট্যাটাস')",
            "val('Category')": "val('Category','Product Category','Type','ক্যাটাগরি','শ্রেণি','ধরন')",
            "val('Subcategory')": "val('Subcategory','Sub Category','Sub-Category','Collection','সাব ক্যাটাগরি')",
            "val('Color')": "val('Color','Colour','রং','কালার')",
            "val('Size')": "val('Size','Sizes','সাইজ')",
            "val('SKU')": "val('SKU','Code','Product Code','কোড')",
            "val('Product URL','Product Link','URL','Link')": "val('Product URL','Product Link','URL','Link','Page URL','Product Page URL','Facebook URL','Post URL','Website URL','পণ্যের লিংক','প্রোডাক্ট লিংক','লিংক')",
            "['Product Image','Image 2','Image 3','Image 4','Image 5'].map(k=>val(k))": "['Product Image','Image 2','Image 3','Image 4','Image 5'].map(k=>val(k, k==='Product Image'?'Image':'', k==='Product Image'?'Photo':'', k==='Product Image'?'ছবি':''))"
        }
        for old, new in replacements.items():
            code = code.replace(old, new)
        n['parameters']['jsCode'] = code
save(cat_path, cat)

# 3) Documentation: visible sheet stays simple; technical helper columns are hidden.
doc_path = ROOT / 'docs/PRODUCT_CATALOG.md'
doc = doc_path.read_text()
extra = '''\n## Merchant-facing sheet layout\n\nThe `Products` tab must remain readable for a shop owner. Existing product sheets are **not destructively rewritten or reordered** during catalog sync. The sync accepts common English/Bangla header aliases and normalizes them in memory before PostgreSQL is updated.\n\nFor a newly-created sheet, the visible columns are intentionally compact: `Product Name`, `Price`, `Product Description`, `Product Image`, `Stock Status`, `Stock Qty`, `Category`, `Subcategory`, `Color`, `Size`, `SKU`, `Product URL`, `Offer`, `Discount`, `Aliases`, `Active`, `Updated At`.\n\nDirect-image helper columns (`Resolved Image ...`, `_Image File ID ...`, `_Image Hash ...`) are internal implementation details. The Apps Script creates them when required and hides them automatically. Old empty `Image 2..5` columns are hidden as well; if the merchant actually puts data in one, it stays visible. Do not infer or write fake Color/Size values back into the merchant sheet; those fields are used only when explicitly supplied.\n'''
if '## Merchant-facing sheet layout' not in doc:
    doc_path.write_text(doc.rstrip() + '\n' + extra)
