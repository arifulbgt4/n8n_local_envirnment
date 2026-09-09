import json
from pathlib import Path

PATH = Path('workflows/modular/05_META_MESSAGING_V4_2.json')
data = json.loads(PATH.read_text())


def node(name):
    for n in data.get('nodes', []):
        if n.get('name') == name:
            return n
    raise SystemExit(f'Missing node: {name}')


# 1) Merchant voice and verified color rules in product-answer prompt.
pa = node('Product Answer AI')
text = pa['parameters'].get('text', '')
marker = 'BUSINESS VOICE RULES:'
if marker not in text:
    text += '''\n\nBUSINESS VOICE RULES:\n- You are speaking AS the merchant/business to its customer. When referring to the business/catalog, use first-person plural: “আমাদের কাছে”, “আমাদের পণ্য”, “আমরা”.\n- NEVER say “আপনাদের কাছে” when you mean the merchant's own stock/catalog. “আপনি/আপনার” may only address the customer.\n- Example: say “আমাদের কাছে বর্তমানে এই শাড়িগুলো আছে:” — never “আপনাদের কাছে বর্তমানে…”.\n\nIMAGE + COLOR RULES:\n- If the customer asks for a specific color and a candidate has an explicit matching `color`, select that exact candidate/variant. Never guess a color from an image.\n- If no candidate has a verified matching color, clearly say the color is not verified; never invent a color.\n- If the customer asks for product photos, return only a short acknowledgement in `reply`; native image attachments are sent by the downstream media branch. Never print image URLs.\n- If the customer asks for all photos / সব ছবি / সবগুলো ছবি / ছবিগুলো / পিকগুলো / all images, acknowledge briefly; the media branch must send every available verified product-media row.\n'''
pa['parameters']['text'] = text

# 2) Cached product replies must also use merchant voice.
hit = node('Product Cache HIT')
code = hit['parameters'].get('jsCode', '')
if 'const merchantVoice=' not in code:
    code = "const merchantVoice=(value)=>String(value||'').replace(/আপনাদের কাছে/g,'আমাদের কাছে').replace(/আপনাদের পণ্য/g,'আমাদের পণ্য').replace(/আপনাদের স্টকে/g,'আমাদের স্টকে');\n" + code
code = code.replace('reply: stripMediaLinks($json.cache_reply)', 'reply: merchantVoice(stripMediaLinks($json.cache_reply))')
hit['parameters']['jsCode'] = code

# 3) Fresh AI product replies must also use merchant voice, and carry more media URLs.
parse = node('Parse Product Answer')
pcode = parse['parameters'].get('jsCode', '')
if 'const merchantVoice=' not in pcode:
    pcode = "const merchantVoice=(value)=>String(value||'').replace(/আপনাদের কাছে/g,'আমাদের কাছে').replace(/আপনাদের পণ্য/g,'আমাদের পণ্য').replace(/আপনাদের স্টকে/g,'আমাদের স্টকে');\n" + pcode
pcode = pcode.replace("reply: stripMediaLinks(o.reply || '')", "reply: merchantVoice(stripMediaLinks(o.reply || ''))")
pcode = pcode.replace('urls.slice(0, 5)', 'urls.slice(0, 10)').replace('urls.slice(0,5)', 'urls.slice(0,10)')
parse['parameters']['jsCode'] = pcode

# 4) Multi-image sender. Important: for plural/all-image requests always enumerate media sort orders,
# even when upstream has only one productImageUrl. The DB resolver then loads image-1..image-10.
img = node('Only Product Image Request')
img['parameters']['jsCode'] = r'''const out=[];
for(const item of $input.all()){
  const j=item.json||{};
  const txt=String(j.normalizedQuestion||j.message||'').toLowerCase().replace(/\s+/g,' ').trim();
  const inferred=/ছবি|ফটো|পিক|image|photo|pic|picture|chobi|chhobi/i.test(txt);
  if(!j.wantsImage&&!inferred)continue;

  const selectedProductId=String(j.selectedProductId||j.contextPatch?.selected_product?.productId||j.context?.selected_product?.productId||'');
  const wantsAll=/(?:সব\s*গুলো|সবগুলো|সব|সকল|all|every)\s*(?:টা|গুলো)?\s*(?:ছবি|পিক|ফটো|image|images|pic|pics|photo|photos|picture|pictures)|(?:ছবিগুলো|পিকগুলো|ফটোগুলো|images|pics|photos|pictures)/i.test(txt);

  const colorMap=[
    ['লাল','red'],['red','red'],['নীল','blue'],['blue','blue'],['সবুজ','green'],['green','green'],
    ['কালো','black'],['black','black'],['সাদা','white'],['white','white'],['হলুদ','yellow'],['yellow','yellow'],
    ['গোলাপি','pink'],['pink','pink'],['মেরুন','maroon'],['maroon','maroon'],['বেগুনি','purple'],['purple','purple'],
    ['কমলা','orange'],['orange','orange'],['ধূসর','gray'],['grey','gray'],['gray','gray'],['বাদামি','brown'],['brown','brown']
  ];
  let requestedColor='';
  for(const [needle,canon] of colorMap){if(txt.includes(needle)){requestedColor=canon;break;}}

  let urls=Array.isArray(j.productImageUrls)?j.productImageUrls.filter(Boolean):[];
  if(!urls.length&&j.productImageUrl)urls=[j.productImageUrl];
  urls=[...new Set(urls.map(String))].slice(0,10);

  if(wantsAll && selectedProductId){
    // Enumerate DB media rows 1..10. Existing rows return; non-existent sort orders naturally drop.
    for(let i=1;i<=10;i++){
      out.push({json:{...j,selectedProductId,productImageUrl:urls[i-1]||'',mediaSortOrder:i,wantsAllImages:true,requestedColor}});
    }
    continue;
  }

  if(urls.length){
    out.push({json:{...j,selectedProductId,productImageUrl:String(urls[0]),mediaSortOrder:1,wantsAllImages:false,requestedColor}});
    continue;
  }

  if(selectedProductId){
    out.push({json:{...j,selectedProductId,productImageUrl:'',mediaSortOrder:1,wantsAllImages:false,requestedColor}});
  }
}
return out;'''

# 5) Add explicit requested-color fields to product-search prompt context if absent.
# The verified candidate `color` field already comes from PostgreSQL; no visual color guessing is allowed.

# Sanity checks.
assert 'BUSINESS VOICE RULES:' in pa['parameters']['text']
assert "আমাদের কাছে" in pa['parameters']['text']
assert 'wantsAllImages' in img['parameters']['jsCode']
assert 'for(let i=1;i<=10;i++)' in img['parameters']['jsCode']
assert 'merchantVoice(stripMediaLinks' in hit['parameters']['jsCode']
assert 'merchantVoice(stripMediaLinks' in parse['parameters']['jsCode']

PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print('Patched merchant voice, verified-color behavior, and multi-image delivery')
