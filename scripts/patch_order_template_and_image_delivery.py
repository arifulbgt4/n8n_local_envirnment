import json
from pathlib import Path

ROOT = Path('.')
WF = ROOT / 'workflows/modular/05_META_MESSAGING_V4_2.json'
SERVER = ROOT / 'services/media-cache/server.mjs'

wf = json.loads(WF.read_text(encoding='utf-8'))
by_name = {n.get('name'): n for n in wf.get('nodes', [])}

def node(name):
    if name not in by_name:
        raise RuntimeError(f'Missing workflow node: {name}')
    return by_name[name]

# 1) Keep order collection conversational while still allowing product/image questions.
node('Quick Intent Router')['parameters']['jsCode'] = r'''const j=$json;
const t=String(j.normalizedQuestion||j.message||'').toLowerCase();
const state=j.conversationState||'BROWSING';
const prev=j.context?.selected_product||null;
const has=(...xs)=>xs.some(x=>t.includes(x));
const wantsImage=has('ছবি','ছবিটা','ছবিগুলো','ফটো','পিক','পিকটা','পিকগুলো','image','images','photo','photos','pic','pics','picture','pictures','chobi','chhobi','chobita','pic dao','pic daw','pic den','photo daw','photo dao');
const productQuestion=has('price','দাম','stock','স্টক','color','কালার','size','সাইজ','material','কাপড়','ছবি','ফটো','পিক','image','photo','pic');
let intent='',needsAI=false;
if(has('যোগাযোগ করবেন না','contact korben na','do not contact','stop followup','stop follow-up','আর প্রয়োজন নেই','লাগবে না','পরে দেখব','stop')) intent='STOP_FOLLOWUP';
else if(has('cancel order','order cancel','অর্ডার বাতিল','ক্যানসেল')) intent='CANCEL_ORDER';
else if(has('order status','status','অর্ডার কোথায়','ডেলিভারি কবে','tracking','ট্র্যাকিং')) intent='ORDER_STATUS';
else if((state==='AWAITING_CONFIRMATION'||state==='ORDER_COLLECTING')&&has('confirm','yes','জি','হ্যাঁ','হ্যা','ঠিক আছে','ok','okay','কনফার্ম')) intent='CONFIRM_ORDER';
else if(has('order korbo','order korte','অর্ডার করব','অর্ডার করতে','কিনবো','কিনব','buy','purchase','নিতে চাই')) intent='CREATE_ORDER';
else if((state==='ORDER_COLLECTING'||state==='AWAITING_CONFIRMATION')&&!productQuestion) intent='CREATE_ORDER';
else if(has('price','দাম','stock','স্টক','ছবি','ফটো','পিক','image','photo','pic','color','কালার','size','সাইজ','material','কাপড়','product','পণ্য','শাড়ি','শাড়ি','saree','shari')) intent='PRODUCT_SEARCH';
else if(prev&&t.length<=45&&has('কত','koto','দাও','daw','ache','আছে','price','দাম','ছবি','পিক','image','pic','stock','স্টক')) intent='PRODUCT_SEARCH';
else needsAI=true;
return [{json:{...j,intent,needsAI,wantsImage}}];'''

# 2) Stronger extraction instructions for Bengali/Banglish address + slot filling.
node('Order Details Extract AI')['parameters']['text'] = r'''=Extract ONLY order details explicitly present in the customer's latest message.
Never invent values. Never extract or guess product price.
Use current draft to understand what is already known and do not erase previously collected values.
Return MINIFIED JSON only with nullable keys:
{"customer_name":null,"phone":null,"product_query":null,"quantity":null,"address":null,"area_name":null,"thana":null,"district":null,"payment_method":null,"note":null}

Message: {{ $json.message }}
Current draft: {{ JSON.stringify($json.draft) }}
Selected product: {{ JSON.stringify($json.selectedProduct) }}
Recent product hints: {{ JSON.stringify($json.productHint) }}
Business payment methods: {{ $json.paymentMethods }}

ORDER SLOT RULES:
- A customer can provide several fields in one message. Extract ALL fields that are clearly present.
- Bengali/Banglish examples such as "জেলা বাগেরহাট থানা মোড়েলগঞ্জ ইউনিয়ন তেলিগাতী" contain district, thana and area_name in one message; extract all three.
- If the customer sends a labelled template such as নাম:, মোবাইল:, জেলা:, থানা:, এলাকা/ইউনিয়ন:, সম্পূর্ণ ঠিকানা:, পরিমাণ:, পেমেন্ট:, extract every filled line.
- If a message starts with "ঠিকানা:" / "Address:" and contains a full delivery address, put the full text after the label in address. If district/thana/area are explicitly identifiable, fill those keys too.
- If the customer says that the locality already supplied is the complete address (for example "হ্যাঁ এটাই সম্পূর্ণ ঠিকানা"), do not ask for the same address again. Preserve the current district/thana/area; address may be the combined explicit locality already present in the draft.
- Never replace a non-empty current draft value with null/empty.
- payment_method may be extracted as COD/Cash on Delivery when the customer explicitly agrees to COD.

VOICE/LANGUAGE GUARD:
- If inputSource is `voice`, interpret Bengali/Banglish naturally. Bengali voice may mix English product names, numbers and place names.
- Never switch to an unrelated language because of uncertain transcription.
Input source: {{ $json.inputSource || 'text' }}
Preferred reply language: {{ $json.preferredReplyLanguage || '' }}'''

# 3) Deterministic safety-net parsing for labels/full address and "this is the complete address".
node('Parse Order Details')['parameters']['jsCode'] = r'''const base=$('Order Context for AI').item.json;
let raw=String($json.text||$json.output||'').trim().replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();
let patch={};
try{patch=JSON.parse(raw)||{};}catch{patch={};}
for(const k of Object.keys(patch)) if(patch[k]===null||patch[k]===undefined||String(patch[k]).trim()==='') delete patch[k];

const msg=String(base.message||'').trim();
const draft=base.draft||{};
const put=(k,v)=>{v=String(v??'').trim().replace(/\s+/g,' ');if(v&&!patch[k])patch[k]=v;};
const line=(labels)=>{
  const re=new RegExp('(?:^|\\n)\\s*(?:'+labels+')\\s*[:：\\-]?\\s*([^\\n]+)','i');
  const m=msg.match(re);return m?m[1].trim():'';
};
const inline=(labels,next)=>{
  const re=new RegExp('(?:'+labels+')\\s*[:：\\-]?\\s*(.+?)(?=\\s+(?:'+next+')\\s*[:：\\-]?|[,;\\n]|$)','i');
  const m=msg.match(re);return m?m[1].trim():'';
};
const bnDigits=s=>String(s||'').replace(/[০-৯]/g,d=>'০১২৩৪৫৬৭৮৯'.indexOf(d));

put('customer_name',line('নাম|নামটি|customer\\s*name|name'));
const phoneLabel=line('মোবাইল|মোবাইল\\s*নম্বর|ফোন|ফোন\\s*নম্বর|mobile|phone');
const phoneAny=bnDigits(msg).match(/(?:\+?88)?01[3-9]\d{8}/)?.[0]||'';
put('phone',bnDigits(phoneLabel)||phoneAny);
put('district',line('জেলা|district')||inline('জেলা|district','থানা|উপজেলা|police\\s*station|ইউনিয়ন|ইউনিয়ন|এলাকা|area|ঠিকানা|address'));
put('thana',line('থানা|উপজেলা|police\\s*station|thana')||inline('থানা|উপজেলা|police\\s*station|thana','ইউনিয়ন|ইউনিয়ন|এলাকা|area|ঠিকানা|address'));
put('area_name',line('এলাকা|এরিয়া|এরিয়া|ইউনিয়ন|ইউনিয়ন|union|area')||inline('ইউনিয়ন|ইউনিয়ন|এলাকা|এরিয়া|এরিয়া|union|area','ঠিকানা|address'));
const addressLine=line('সম্পূর্ণ\\s*ঠিকানা|ডেলিভারি\\s*ঠিকানা|ঠিকানা|full\\s*address|delivery\\s*address|address');
if(addressLine){
  put('address',addressLine);
  const parts=addressLine.split(/[,،;|]/).map(x=>x.trim()).filter(Boolean);
  if(parts.length>=3){
    if(!patch.district&&!draft.district)patch.district=parts[0];
    if(!patch.thana&&!draft.thana)patch.thana=parts[1];
    if(!patch.area_name&&!draft.area_name)patch.area_name=parts[2];
  }
}
const qty=line('পরিমাণ|quantity|qty');
if(qty){const n=Number(bnDigits(qty).match(/\d+/)?.[0]||0);if(n>0&&!patch.quantity)patch.quantity=n;}
const pay=line('পেমেন্ট|পেমেন্ট\\s*মেথড|payment|payment\\s*method');
put('payment_method',pay);
if(!patch.payment_method&&/\bCOD\b|cash\s*on\s*delivery|ক্যাশ\s*অন\s*ডেলিভারি/i.test(msg))patch.payment_method='COD';

const confirmsComplete=/এটাই\s*(?:আমার\s*)?সম্পূর্ণ\s*ঠিকানা|এইটাই\s*(?:আমার\s*)?সম্পূর্ণ\s*ঠিকানা|this\s+is\s+(?:my\s+)?complete\s+address/i.test(msg);
if(confirmsComplete&&!patch.address&&!draft.address){
  const merged={...draft,...patch};
  const combined=[merged.area_name,merged.thana,merged.district].filter(Boolean).join(', ');
  if(combined)patch.address=combined;
}

const methods=String(base.paymentMethods||'').split(/[,|/]/).map(x=>x.trim()).filter(Boolean);
if(!patch.payment_method&&!draft.payment_method&&methods.length===1)patch.payment_method=methods[0];
return [{json:{...base,orderPatch:patch}}];'''

# 4) Human-friendly fill-in template instead of repeating one hard-coded question forever.
node('Build Order Collection Reply')['parameters']['jsCode'] = r'''const base=$json.base;
const d={...($json.draft||{})};
const oneMethod=String(base.paymentMethods||'').split(/[,|/]/).map(x=>x.trim()).filter(Boolean);
if(!d.payment_method&&oneMethod.length===1)d.payment_method=oneMethod[0];
const blank=k=>d[k]===undefined||d[k]===null||String(d[k]).trim()==='';
const productName=$json.verified_product_name||d.product_name||'';

if(blank('product_id')){
  return [{json:{...base,reply:'কোন পণ্যটি অর্ডার করতে চান? পণ্যের নাম লিখুন বা ছবিটি পাঠান।',state:'ORDER_COLLECTING',scheduleFollowup:true,contextPatch:{order_draft:d}}}];
}

const fields=[
  ['customer_name','নাম'],['phone','মোবাইল'],['district','জেলা'],['thana','থানা'],['area_name','এলাকা/ইউনিয়ন'],['address','সম্পূর্ণ ঠিকানা'],['quantity','পরিমাণ'],['payment_method','পেমেন্ট']
];
const missing=fields.filter(([k])=>blank(k)).map(([k])=>k);
let reply,state='ORDER_COLLECTING',scheduleFollowup=true;
if(missing.length){
  const show=(k,fallback='________')=>blank(k)?fallback:String(d[k]);
  reply=`অর্ডার কনফার্ম করতে নিচের টেমপ্লেটটি পূরণ করে এক মেসেজে পাঠান। আগে দেওয়া তথ্যগুলো রাখা আছে—শুধু ফাঁকা অংশ পূরণ করলেই হবে।\n\nপণ্য: ${productName}\nনাম: ${show('customer_name')}\nমোবাইল: ${show('phone')}\nজেলা: ${show('district')}\nথানা: ${show('thana')}\nএলাকা/ইউনিয়ন: ${show('area_name')}\nসম্পূর্ণ ঠিকানা: ${show('address')}\nপরিমাণ: ${show('quantity')}\nপেমেন্ট: ${show('payment_method',base.paymentMethods||'________')}`;
}else{
  const q=Math.max(1,Number(d.quantity||1));
  const price=Number($json.verified_price||0);
  const delivery=Number(base.deliveryCharge||0);
  const subtotal=q*price;
  const total=subtotal+delivery;
  reply=`অর্ডারের তথ্যগুলো যাচাই করুন:\n\nনাম: ${d.customer_name}\nমোবাইল: ${d.phone}\nপণ্য: ${productName}\nপরিমাণ: ${q}\nঠিকানা: ${d.address}, ${d.area_name}, ${d.thana}, ${d.district}\nপণ্যের মূল্য: ${subtotal} টাকা\nডেলিভারি চার্জ: ${delivery} টাকা\nমোট: ${total} টাকা\nপেমেন্ট: ${d.payment_method}\n\nসব ঠিক থাকলে “Confirm” / “হ্যাঁ” লিখুন।`;
  state='AWAITING_CONFIRMATION';
}
return [{json:{...base,reply,state,scheduleFollowup,contextPatch:{order_draft:d},missingOrderFields:missing}}];'''

# 5) Image requests must not silently die when productImageUrls was not propagated.
node('Only Product Image Request')['parameters']['jsCode'] = r'''const out=[];
for(const item of $input.all()){
  const j=item.json||{};
  const txt=String(j.normalizedQuestion||j.message||'').toLowerCase();
  const inferred=/ছবি|ফটো|পিক|image|photo|pic|picture|chobi|chhobi/i.test(txt);
  if(!j.wantsImage&&!inferred)continue;
  const selectedProductId=String(j.selectedProductId||j.contextPatch?.selected_product?.productId||j.context?.selected_product?.productId||'');
  let urls=Array.isArray(j.productImageUrls)?j.productImageUrls.filter(Boolean):[];
  if(!urls.length&&j.productImageUrl)urls=[j.productImageUrl];
  urls=[...new Set(urls)].slice(0,5);
  if(urls.length){
    urls.forEach((url,i)=>out.push({json:{...j,selectedProductId,productImageUrl:String(url),mediaSortOrder:i+1}}));
    continue;
  }
  if(selectedProductId){
    const plural=/ছবিগুলো|পিকগুলো|images|photos|pics|pictures/i.test(txt);
    const count=plural?5:1;
    for(let i=1;i<=count;i++)out.push({json:{...j,selectedProductId,productImageUrl:'',mediaSortOrder:i}});
  }
}
return out;'''

# 6) If the URL was lost in upstream data, look up the product_media row by sort_order.
node('Load Product Media Send Cache')['parameters']['query'] = """WITH input AS (SELECT $4::jsonb AS base), pm AS (\n  SELECT * FROM product_media\n  WHERE product_id=NULLIF($1,'')::bigint\n    AND active=TRUE\n    AND (\n      (NULLIF($3,'') IS NOT NULL AND resolved_url=$3)\n      OR sort_order=$2::int\n    )\n  ORDER BY CASE WHEN NULLIF($3,'') IS NOT NULL AND resolved_url=$3 THEN 0 ELSE 1 END,sort_order\n  LIMIT 1\n)\nSELECT input.base,pm.id::text AS media_row_id,pm.media_key,pm.resolved_url,COALESCE(pm.cache_key,'') AS cache_key,COALESCE(pm.local_path,'') AS local_path,COALESCE(pm.mime_type,'') AS mime_type,COALESCE(pm.file_size,0)::text AS file_size,COALESCE(pm.facebook_attachment_id,'') AS facebook_attachment_id\nFROM input JOIN pm ON TRUE;"""

# 7) Retry image delivery; failures should be visible instead of a silent "sending image" text only.
fb = node('Send Facebook Product Image Cached')
fb['retryOnFail'] = True
fb['maxTries'] = 3
fb['waitBetweenTries'] = 1000
fb.pop('continueOnFail', None)

# Preserve valid legacy non-Facebook image sender but don't swallow failure.
legacy = node('Send Verified Product Image')
legacy.pop('continueOnFail', None)
legacy['retryOnFail'] = True
legacy['maxTries'] = 2
legacy['waitBetweenTries'] = 1000

WF.write_text(json.dumps(wf, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# 8) Strengthen the local persistent media service: reuse local file directly and fall back
# to a native URL attachment (link is never shown as customer-facing text) if reusable upload fails.
text = SERVER.read_text(encoding='utf-8')
if 'async function sendUrlAttachment' not in text:
    marker = "async function uploadReusableAttachment({ accessToken, localPath, mimeType, graphVersion }) {"
    insert = r'''async function sendUrlAttachment({ accessToken, recipientId, sourceUrl, graphVersion }) {
  return graphJson(`https://graph.facebook.com/${graphVersion}/me/messages`, accessToken, {
    recipient: { id: String(recipientId) },
    messaging_type: 'RESPONSE',
    message: { attachment: { type: 'image', payload: { url: String(sourceUrl), is_reusable: true } } },
  });
}

'''
    if marker not in text:
        raise RuntimeError('media-cache uploadReusableAttachment marker not found')
    text = text.replace(marker, insert + marker, 1)

start = text.index('async function handleFacebookSend(body) {')
end = text.index('\nconst server = http.createServer', start)
new_handle = r'''async function handleFacebookSend(body) {
  const accessToken = String(body.accessToken || '');
  const recipientId = String(body.recipientId || '');
  const sourceUrl = String(body.sourceUrl || '');
  const graphVersion = String(body.graphVersion || DEFAULT_GRAPH_VERSION).replace(/^\/+/, '');
  let attachmentId = String(body.attachmentId || '');
  if (!accessToken || !recipientId) throw new Error('accessToken and recipientId are required');

  if (attachmentId) {
    try {
      const sent = await sendAttachmentId({ accessToken, recipientId, attachmentId, graphVersion });
      return {
        ok: true,
        messageId: String(sent.message_id || ''),
        attachmentId,
        reusedAttachment: true,
        reusedLocalFile: true,
        cacheKey: String(body.cacheKey || ''),
        localPath: String(body.localPath || ''),
        mimeType: String(body.mimeType || ''),
        fileSize: Number(body.fileSize || 0),
      };
    } catch {
      attachmentId = '';
    }
  }

  let cached = null;
  const suppliedLocalPath = String(body.localPath || '');
  if (suppliedLocalPath && await exists(suppliedLocalPath)) {
    const stat = await fs.stat(suppliedLocalPath);
    cached = {
      cacheKey: String(body.cacheKey || safeKey(suppliedLocalPath)),
      localPath: suppliedLocalPath,
      mimeType: String(body.mimeType || 'image/jpeg'),
      fileSize: stat.size,
      reusedLocalFile: true,
    };
  } else {
    if (!sourceUrl) throw new Error('sourceUrl is required when no reusable attachmentId/local file is available');
    cached = await cacheImage(sourceUrl, body.cacheKey);
  }

  try {
    attachmentId = await uploadReusableAttachment({
      accessToken,
      localPath: cached.localPath,
      mimeType: cached.mimeType,
      graphVersion,
    });
    const sent = await sendAttachmentId({ accessToken, recipientId, attachmentId, graphVersion });
    return {
      ok: true,
      messageId: String(sent.message_id || ''),
      attachmentId,
      reusedAttachment: false,
      ...cached,
    };
  } catch (uploadError) {
    if (!sourceUrl) throw uploadError;
    const sent = await sendUrlAttachment({ accessToken, recipientId, sourceUrl, graphVersion });
    return {
      ok: true,
      messageId: String(sent.message_id || ''),
      attachmentId: '',
      reusedAttachment: false,
      fallbackUrlAttachment: true,
      ...cached,
    };
  }
}
'''
text = text[:start] + new_handle + text[end:]
SERVER.write_text(text, encoding='utf-8')

print('Order template/address extraction and image-delivery reliability patch applied')
