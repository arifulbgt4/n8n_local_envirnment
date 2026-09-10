import json
import re
from pathlib import Path
from uuid import uuid4

ROOT = Path('.')

AI_COLUMNS = [
    'AI API Key',
    'AI Base URL',
    'AI Audio Provider',
    'AI Audio Model',
    'AI Audio API Key',
    'AI Audio Base URL',
]

SCHEMA_COLUMNS = """  ai_provider TEXT,
  ai_model TEXT,
  ai_api_key TEXT,
  ai_base_url TEXT,
  ai_audio_provider TEXT,
  ai_audio_model TEXT,
  ai_audio_api_key TEXT,
  ai_audio_base_url TEXT,
  ai_prompt_override TEXT NOT NULL DEFAULT '',"""

SCHEMA_MIGRATION = """
-- Dynamic per-account AI provider/model credentials. No provider or model default is enforced by n8n.
ALTER TABLE business_accounts ADD COLUMN IF NOT EXISTS ai_api_key TEXT;
ALTER TABLE business_accounts ADD COLUMN IF NOT EXISTS ai_base_url TEXT;
ALTER TABLE business_accounts ADD COLUMN IF NOT EXISTS ai_audio_provider TEXT;
ALTER TABLE business_accounts ADD COLUMN IF NOT EXISTS ai_audio_model TEXT;
ALTER TABLE business_accounts ADD COLUMN IF NOT EXISTS ai_audio_api_key TEXT;
ALTER TABLE business_accounts ADD COLUMN IF NOT EXISTS ai_audio_base_url TEXT;
ALTER TABLE business_accounts ALTER COLUMN ai_provider DROP DEFAULT;
ALTER TABLE business_accounts ALTER COLUMN ai_model DROP DEFAULT;
ALTER TABLE business_accounts ALTER COLUMN ai_provider DROP NOT NULL;
ALTER TABLE business_accounts ALTER COLUMN ai_model DROP NOT NULL;
"""


def modernize_schema(text: str) -> str:
    patterns = [
        "  ai_provider TEXT NOT NULL DEFAULT 'openai',\n  ai_model TEXT NOT NULL DEFAULT 'gpt-5.6-luna',\n  ai_prompt_override TEXT NOT NULL DEFAULT '',",
        "  ai_provider TEXT,\n  ai_model TEXT,\n  ai_prompt_override TEXT NOT NULL DEFAULT '',",
    ]
    for old in patterns:
        if old in text:
            text = text.replace(old, SCHEMA_COLUMNS, 1)
            break
    if 'ai_api_key TEXT' not in text:
        raise RuntimeError('Could not add dynamic AI columns to schema')
    if '-- Dynamic per-account AI provider/model credentials.' not in text:
        text += '\n' + SCHEMA_MIGRATION
    return text


for filename in [
    'init-db/001-init.sql',
    'docs/DATABASE_SCHEMA.sql',
    'docs/RESET_APPLICATION_DATABASE.sql',
]:
    p = Path(filename)
    p.write_text(modernize_schema(p.read_text(encoding='utf-8')), encoding='utf-8')

# --- Setup workflow: DB migration + append account AI fields without shifting existing columns. ---
setup_path = Path('workflows/modular/01_SETUP_CONFIG_V4_2.json')
setup = json.loads(setup_path.read_text(encoding='utf-8'))
setup_nodes = {n['name']: n for n in setup['nodes']}
schema_node = setup_nodes['02.02 - Apply / Migrate Database Schema']
schema_node['parameters']['query'] = modernize_schema(schema_node['parameters']['query'])

headers_node = setup_nodes['02.05 - Build Missing Control Tabs']
code = headers_node['parameters']['jsCode']
m = re.search(r'("02_ACCOUNTS"\s*:\s*\[)(.*?)(\])', code)
if not m:
    raise RuntimeError('Could not locate 02_ACCOUNTS headers')
existing_headers = json.loads('[' + m.group(2) + ']')
for col in AI_COLUMNS:
    if col not in existing_headers:
        existing_headers.append(col)
new_inner = ', '.join(json.dumps(x) for x in existing_headers)
code = code[:m.start(2)] + new_inner + code[m.end(2):]
headers_node['parameters']['jsCode'] = code
setup_path.write_text(json.dumps(setup, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

# --- Control sync: spreadsheet provider/model/key -> account DB columns. ---
sync_path = Path('workflows/modular/01B_CONTROL_SYNC_V4_2.json')
sync = json.loads(sync_path.read_text(encoding='utf-8'))
sync_nodes = {n['name']: n for n in sync['nodes']}
read_accounts = sync_nodes['03.05 - Read Accounts']
read_accounts['parameters']['url'] = read_accounts['parameters']['url'].replace('02_ACCOUNTS!A:AF', '02_ACCOUNTS!A:AL')

sync_nodes['03.06 - Parse + Validate Accounts']['parameters']['jsCode'] = r"""const v=$json.values||[];
if(v.length<1)return[{json:{rows:[]}}];
const h=v[0];
const bool=(x,d=false)=>x===''||x===null||x===undefined?d:!['false','0','no','off'].includes(String(x).trim().toLowerCase());
const num=(x,d)=>{const n=Number(x);return Number.isFinite(n)?n:d};
const rows=v.slice(1).map((r,i)=>{
  const x=Object.fromEntries(h.map((k,j)=>[String(k||'').trim(),r[j]??'']));
  return {
    account_key:String(x['Account Key']||'').trim(),
    business_id:String(x['Business Key']||'').trim(),
    platform:String(x['Platform']||'').trim().toLowerCase(),
    account_name:String(x['Account Name']||'').trim(),
    external_account_id:String(x['External Account ID']||'').trim(),
    meta_app_id:String(x['Meta App ID']||'').trim(),
    facebook_page_id:String(x['Facebook Page ID']||'').trim(),
    instagram_account_id:String(x['Instagram Account ID']||'').trim(),
    whatsapp_phone_number_id:String(x['WhatsApp Phone Number ID']||'').trim(),
    whatsapp_business_account_id:String(x['WhatsApp Business Account ID']||'').trim(),
    meta_app_secret:String(x['Meta App Secret']||'').trim(),
    access_token:String(x['Access Token']||'').trim(),
    verify_token:String(x['Verify Token']||'').trim(),
    operations_spreadsheet_id:String(x['Operations Spreadsheet ID']||'').trim(),
    auto_create_spreadsheet:bool(x['Auto Create Spreadsheet'],false),
    graph_api_version:String(x['Graph API Version']||'v26.0').trim(),
    reply_url:String(x['Reply URL']||'').trim(),
    conversation_url_template:String(x['Conversation URL Template']||'').trim(),
    ai_provider:String(x['AI Provider']||'').trim().toLowerCase(),
    ai_model:String(x['AI Model']||'').trim(),
    ai_api_key:String(x['AI API Key']||'').trim(),
    ai_base_url:String(x['AI Base URL']||'').trim(),
    ai_audio_provider:String(x['AI Audio Provider']||'').trim().toLowerCase(),
    ai_audio_model:String(x['AI Audio Model']||'').trim(),
    ai_audio_api_key:String(x['AI Audio API Key']||'').trim(),
    ai_audio_base_url:String(x['AI Audio Base URL']||'').trim(),
    ai_prompt_override:String(x['AI Prompt Override']||'').trim(),
    max_messages_per_minute:num(x['Max Messages Per Minute'],8),
    max_ai_turns_per_hour:num(x['Max AI Turns Per Hour'],20),
    max_ai_turns_per_day:num(x['Max AI Turns Per Day'],100),
    estimated_tokens_per_turn:num(x['Estimated Tokens Per Turn'],1800),
    max_estimated_tokens_per_day:num(x['Max Estimated Tokens Per Day'],100000),
    followup_enabled_default:bool(x['Followup Enabled'],true),
    followup_1_minutes:num(x['Followup 1 Minutes'],60),
    followup_2_minutes:num(x['Followup 2 Minutes'],1440),
    auto_human_on_manual_reply:bool(x['Auto Human On Manual Reply'],true),
    active:bool(x['Active'],true),
    control_row_number:i+2
  };
}).filter(x=>x.account_key&&x.business_id&&['facebook','instagram','whatsapp'].includes(x.platform)&&x.external_account_id);
return[{json:{rows}}];"""

sync_nodes['03.07 - Upsert Accounts']['parameters']['query'] = SCHEMA_MIGRATION + r"""
WITH x AS (
  SELECT * FROM jsonb_to_recordset($1::jsonb) AS t(
    account_key text,business_id text,platform text,account_name text,external_account_id text,
    meta_app_id text,facebook_page_id text,instagram_account_id text,whatsapp_phone_number_id text,
    whatsapp_business_account_id text,meta_app_secret text,access_token text,verify_token text,
    operations_spreadsheet_id text,auto_create_spreadsheet boolean,graph_api_version text,reply_url text,
    conversation_url_template text,ai_provider text,ai_model text,ai_api_key text,ai_base_url text,
    ai_audio_provider text,ai_audio_model text,ai_audio_api_key text,ai_audio_base_url text,
    ai_prompt_override text,max_messages_per_minute int,max_ai_turns_per_hour int,max_ai_turns_per_day int,
    estimated_tokens_per_turn int,max_estimated_tokens_per_day int,followup_enabled_default boolean,
    followup_1_minutes int,followup_2_minutes int,auto_human_on_manual_reply boolean,active boolean,control_row_number int
  )
)
INSERT INTO business_accounts(
  account_key,business_id,platform,account_name,external_account_id,meta_app_id,facebook_page_id,
  instagram_account_id,whatsapp_phone_number_id,whatsapp_business_account_id,meta_app_secret,access_token,
  verify_token,operations_spreadsheet_id,auto_create_spreadsheet,graph_api_version,reply_url,
  conversation_url_template,ai_provider,ai_model,ai_api_key,ai_base_url,ai_audio_provider,ai_audio_model,
  ai_audio_api_key,ai_audio_base_url,ai_prompt_override,max_messages_per_minute,max_ai_turns_per_hour,
  max_ai_turns_per_day,estimated_tokens_per_turn,max_estimated_tokens_per_day,followup_enabled_default,
  followup_1_minutes,followup_2_minutes,auto_human_on_manual_reply,active,control_row_number,updated_at
)
SELECT
  account_key,business_id,platform,account_name,external_account_id,meta_app_id,facebook_page_id,
  instagram_account_id,whatsapp_phone_number_id,whatsapp_business_account_id,NULLIF(meta_app_secret,''),NULLIF(access_token,''),
  verify_token,operations_spreadsheet_id,auto_create_spreadsheet,graph_api_version,
  COALESCE(NULLIF(reply_url,''),CASE WHEN platform IN ('facebook','instagram') THEN 'https://graph.facebook.com/'||graph_api_version||'/me/messages' WHEN platform='whatsapp' THEN 'https://graph.facebook.com/'||graph_api_version||'/'||whatsapp_phone_number_id||'/messages' ELSE NULL END),
  conversation_url_template,NULLIF(ai_provider,''),NULLIF(ai_model,''),NULLIF(ai_api_key,''),NULLIF(ai_base_url,''),
  NULLIF(ai_audio_provider,''),NULLIF(ai_audio_model,''),NULLIF(ai_audio_api_key,''),NULLIF(ai_audio_base_url,''),
  ai_prompt_override,max_messages_per_minute,max_ai_turns_per_hour,max_ai_turns_per_day,estimated_tokens_per_turn,
  max_estimated_tokens_per_day,followup_enabled_default,followup_1_minutes,followup_2_minutes,
  auto_human_on_manual_reply,active,control_row_number,NOW()
FROM x
ON CONFLICT(account_key) DO UPDATE SET
  business_id=EXCLUDED.business_id,
  platform=EXCLUDED.platform,
  account_name=EXCLUDED.account_name,
  external_account_id=EXCLUDED.external_account_id,
  meta_app_id=EXCLUDED.meta_app_id,
  facebook_page_id=EXCLUDED.facebook_page_id,
  instagram_account_id=EXCLUDED.instagram_account_id,
  whatsapp_phone_number_id=EXCLUDED.whatsapp_phone_number_id,
  whatsapp_business_account_id=EXCLUDED.whatsapp_business_account_id,
  meta_app_secret=CASE WHEN COALESCE(EXCLUDED.meta_app_secret,'')<>'' THEN EXCLUDED.meta_app_secret ELSE business_accounts.meta_app_secret END,
  access_token=CASE WHEN COALESCE(EXCLUDED.access_token,'')<>'' THEN EXCLUDED.access_token ELSE business_accounts.access_token END,
  verify_token=EXCLUDED.verify_token,
  operations_spreadsheet_id=EXCLUDED.operations_spreadsheet_id,
  auto_create_spreadsheet=EXCLUDED.auto_create_spreadsheet,
  graph_api_version=EXCLUDED.graph_api_version,
  reply_url=EXCLUDED.reply_url,
  conversation_url_template=EXCLUDED.conversation_url_template,
  ai_provider=EXCLUDED.ai_provider,
  ai_model=EXCLUDED.ai_model,
  ai_api_key=CASE WHEN COALESCE(EXCLUDED.ai_api_key,'')<>'' THEN EXCLUDED.ai_api_key ELSE business_accounts.ai_api_key END,
  ai_base_url=EXCLUDED.ai_base_url,
  ai_audio_provider=EXCLUDED.ai_audio_provider,
  ai_audio_model=EXCLUDED.ai_audio_model,
  ai_audio_api_key=CASE WHEN COALESCE(EXCLUDED.ai_audio_api_key,'')<>'' THEN EXCLUDED.ai_audio_api_key ELSE business_accounts.ai_audio_api_key END,
  ai_audio_base_url=EXCLUDED.ai_audio_base_url,
  ai_prompt_override=EXCLUDED.ai_prompt_override,
  max_messages_per_minute=EXCLUDED.max_messages_per_minute,
  max_ai_turns_per_hour=EXCLUDED.max_ai_turns_per_hour,
  max_ai_turns_per_day=EXCLUDED.max_ai_turns_per_day,
  estimated_tokens_per_turn=EXCLUDED.estimated_tokens_per_turn,
  max_estimated_tokens_per_day=EXCLUDED.max_estimated_tokens_per_day,
  followup_enabled_default=EXCLUDED.followup_enabled_default,
  followup_1_minutes=EXCLUDED.followup_1_minutes,
  followup_2_minutes=EXCLUDED.followup_2_minutes,
  auto_human_on_manual_reply=EXCLUDED.auto_human_on_manual_reply,
  active=EXCLUDED.active,
  control_row_number=EXCLUDED.control_row_number,
  updated_at=NOW();
SELECT COUNT(*)::int AS active_accounts FROM business_accounts WHERE active=TRUE;
"""
sync_path.write_text(json.dumps(sync, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

# --- Messaging workflow: remove static provider nodes and route all AI calls through the local dynamic gateway. ---
msg_path = Path('workflows/modular/05_META_MESSAGING_V4_2.json')
msg = json.loads(msg_path.read_text(encoding='utf-8'))
nodes = msg['nodes']
connections = msg['connections']
by_name = {n['name']: n for n in nodes}

base = by_name['Build Base Context']
base_code = base['parameters']['jsCode']
base_code = base_code.replace("aiProvider:j.ai_provider||'openai',aiModel:j.ai_model||'gpt-5.6-luna'", "aiProvider:j.ai_provider||'',aiModel:j.ai_model||''")
base['parameters']['jsCode'] = base_code


def renderer_code(key: str, preserve_binary: bool = False) -> str:
    tail = ',binary:$binary' if preserve_binary else ''
    return f"""const j=$json;\nconst promptKey='{key}';\nconst registry=(j.aiPrompts&&typeof j.aiPrompts==='object'&&!Array.isArray(j.aiPrompts))?j.aiPrompts:{{}};\nconst template=String(registry[promptKey]||'').trim();\nif(!template) throw new Error(`Missing active AI prompt ${{promptKey}} for account ${{j.accountId||j.account_id||'unknown'}}. Configure it in Control Spreadsheet tab 03_AI_PROMPTS.`);\nconst getPath=(obj,path)=>{{const clean=String(path||'').replace(/^\\$json\\./,'');return clean.split('.').filter(Boolean).reduce((v,k)=>v==null?undefined:v[k],obj);}};\nconst rendered=template.replace(/\\{{\\{{\\s*([A-Za-z0-9_.$-]+)\\s*\\}}\\}}/g,(_,path)=>{{const v=getPath(j,path);if(v===undefined||v===null)return '';return typeof v==='object'?JSON.stringify(v):String(v);}});\nreturn [{{json:{{...j,_renderedAiPrompt:rendered,_activePromptKey:promptKey,_aiPurpose:promptKey}}{tail}}}];"""

renderer_defs = {
    'INTENT_CLASSIFIER': ('Render AI Prompt - INTENT_CLASSIFIER', False),
    'PRODUCT_SEARCH_RESPONSE': ('Render AI Prompt - PRODUCT_SEARCH_RESPONSE', False),
    'ORDER_DETAILS_EXTRACT_AI': ('Render AI Prompt - ORDER_DETAILS_EXTRACT_AI', False),
    'GENERAL_ANSWER_AI': ('Render AI Prompt - GENERAL_ANSWER_AI', False),
    'IMAGE_PRODUCT_ANALYSIS': ('Render AI Prompt - IMAGE_PRODUCT_ANALYSIS', True),
}
for key, (name, preserve) in renderer_defs.items():
    if name not in by_name:
        raise RuntimeError(f'Missing prompt renderer: {name}')
    by_name[name]['parameters']['jsCode'] = renderer_code(key, preserve)

# Remove static OpenAI/LangChain execution nodes. Renderers and parsers remain.
remove_names = {
    'OpenAI Chat Model - Core',
    'AI Intent Classifier',
    'Product Answer AI',
    'Order Details Extract AI',
    'General Answer AI',
    'Analyze Product Image',
    'Transcribe Voice',
}
missing = [n for n in remove_names if n not in by_name]
if missing:
    raise RuntimeError(f'Expected legacy AI nodes were not found: {missing}')

nodes[:] = [n for n in nodes if n['name'] not in remove_names]

for source in list(connections.keys()):
    if source in remove_names:
        del connections[source]
        continue
    spec = connections[source]
    for kind, outputs in list(spec.items()):
        if not isinstance(outputs, list):
            continue
        for output in outputs:
            if isinstance(output, list):
                output[:] = [edge for edge in output if edge.get('node') not in remove_names]

by_name = {n['name']: n for n in nodes}

# Reusable n8n nodes for dynamic gateway calls.
def add_node(node):
    if node['name'] in by_name:
        by_name[node['name']].update(node)
        return by_name[node['name']]
    nodes.append(node)
    by_name[node['name']] = node
    return node


def set_main(source: str, target: str):
    connections[source] = {'main': [[{'node': target, 'type': 'main', 'index': 0}]]}


def call_node(key: str, x: int, y: int):
    return {
        'parameters': {
            'method': 'POST',
            'url': 'http://ai-gateway:3002/v1/generate',
            'sendBody': True,
            'contentType': 'raw',
            'rawContentType': 'application/json',
            'body': "={{ JSON.stringify({ accountId: $json.accountId, purpose: $json._activePromptKey, prompt: $json._renderedAiPrompt, inputType: $json._aiInputType || 'text', mediaBase64: $json._aiMediaBase64 || '', mediaMimeType: $json._aiMediaMimeType || '' }) }}",
            'options': {'timeout': 120000},
        },
        'id': str(uuid4()),
        'name': f'Call Dynamic AI - {key}',
        'type': 'n8n-nodes-base.httpRequest',
        'typeVersion': 4.2,
        'position': [x, y],
    }


def normalize_node(key: str, renderer_name: str, x: int, y: int):
    js = f"""const base=$('{renderer_name}').item.json;\nconst r=$json||{{}};\nif(r.ok===false)throw new Error(String(r.error||'Dynamic AI gateway failed'));\nconst aiText=String(r.text||'').trim();\nif(!aiText)throw new Error('Dynamic AI gateway returned empty text for {key}');\nreturn [{{json:{{...base,output:aiText,text:aiText,content:aiText,response:aiText,aiText,aiProviderUsed:String(r.provider||''),aiModelUsed:String(r.model||''),aiUsage:r.usage||{{}},aiPurpose:'{key}'}}}}];"""
    return {
        'parameters': {'jsCode': js},
        'id': str(uuid4()),
        'name': f'Normalize Dynamic AI - {key}',
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [x, y],
    }


def prepare_media_node(key: str, input_type: str, x: int, y: int):
    default_mime = 'image/jpeg' if input_type == 'image' else 'audio/mpeg'
    js = f"""const j=$json;\nconst buffer=await this.helpers.getBinaryDataBuffer(0,'data');\nconst meta=$binary?.data||{{}};\nreturn [{{json:{{...j,_aiInputType:'{input_type}',_aiMediaBase64:buffer.toString('base64'),_aiMediaMimeType:String(meta.mimeType||'{default_mime}')}}}}];"""
    return {
        'parameters': {'jsCode': js},
        'id': str(uuid4()),
        'name': f'Prepare Media AI - {key}',
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [x, y],
    }

# Text AI purposes.
text_routes = [
    ('INTENT_CLASSIFIER', 'Render AI Prompt - INTENT_CLASSIFIER', 'Parse AI Intent', 2280, 160),
    ('PRODUCT_SEARCH_RESPONSE', 'Render AI Prompt - PRODUCT_SEARCH_RESPONSE', 'Parse Product Answer', 3720, -140),
    ('ORDER_DETAILS_EXTRACT_AI', 'Render AI Prompt - ORDER_DETAILS_EXTRACT_AI', 'Parse Order Details', 3720, -80),
    ('GENERAL_ANSWER_AI', 'Render AI Prompt - GENERAL_ANSWER_AI', 'Parse General Answer', 3720, 540),
]
for key, renderer, downstream, x, y in text_routes:
    call = add_node(call_node(key, x, y))
    norm = add_node(normalize_node(key, renderer, x + 220, y))
    set_main(renderer, call['name'])
    set_main(call['name'], norm['name'])
    set_main(norm['name'], downstream)

# Image AI purpose.
image_key = 'IMAGE_PRODUCT_ANALYSIS'
image_renderer = 'Render AI Prompt - IMAGE_PRODUCT_ANALYSIS'
image_prep = add_node(prepare_media_node(image_key, 'image', 1240, 120))
image_call = add_node(call_node(image_key, 1460, 120))
image_norm = add_node(normalize_node(image_key, image_renderer, 1680, 120))
set_main('Only Image Binary', image_renderer)
set_main(image_renderer, image_prep['name'])
set_main(image_prep['name'], image_call['name'])
set_main(image_call['name'], image_norm['name'])
set_main(image_norm['name'], 'Attach Image Analysis')

# Voice transcription is also prompt-driven and dynamically provider/model selected.
voice_key = 'VOICE_TRANSCRIPTION'
voice_renderer_name = 'Render AI Prompt - VOICE_TRANSCRIPTION'
voice_renderer = add_node({
    'parameters': {'jsCode': renderer_code(voice_key, True)},
    'id': str(uuid4()),
    'name': voice_renderer_name,
    'type': 'n8n-nodes-base.code',
    'typeVersion': 2,
    'position': [1060, 280],
})
voice_prep = add_node(prepare_media_node(voice_key, 'audio', 1240, 280))
voice_call = add_node(call_node(voice_key, 1460, 280))
voice_norm = add_node(normalize_node(voice_key, voice_renderer_name, 1680, 280))
set_main('Only Audio Binary', voice_renderer_name)
set_main(voice_renderer_name, voice_prep['name'])
set_main(voice_prep['name'], voice_call['name'])
set_main(voice_call['name'], voice_norm['name'])
set_main(voice_norm['name'], 'Attach Voice Transcript')

# Ensure no fixed provider execution node remains.
serialized = json.dumps(msg, ensure_ascii=False, separators=(',', ':'))
for forbidden in [
    '@n8n/n8n-nodes-langchain.openAi',
    'lmChatOpenAi',
    'OpenAI Chat Model - Core',
    'Describe only visible product-identifying details for catalog search',
]:
    if forbidden in serialized:
        raise RuntimeError(f'Fixed OpenAI/provider artifact remains in messaging workflow: {forbidden}')
msg_path.write_text(serialized + '\n', encoding='utf-8')

# --- Docs ---
docs_path = Path('docs/CONTROL_SPREADSHEET.md')
docs = docs_path.read_text(encoding='utf-8')
provider_section = """

## Dynamic AI provider/model per account

AI execution is provider-agnostic. `05 Meta Messaging` contains no fixed OpenAI/Gemini/Anthropic model node and no static AI credential. The internal `ai-gateway` reads the selected account configuration from PostgreSQL and calls the configured provider.

The following columns are appended to `02_ACCOUNTS` so existing rows do not shift:

- `AI API Key` — secret key for the primary provider.
- `AI Base URL` — optional API root; required for `openai_compatible`.
- `AI Audio Provider` — optional voice-only provider override.
- `AI Audio Model` — optional voice/transcription model override.
- `AI Audio API Key` — optional voice-only secret; blank falls back to the primary key.
- `AI Audio Base URL` — optional voice-only API root.

`AI Provider` accepts `openai`, `anthropic`/`claude`, `gemini`/`google`, and `openai_compatible`. `AI Model` is the exact provider model ID and has no n8n default. Different account/page rows can use completely different providers, models, keys, and base URLs.

For voice messages, the audio override is useful when the primary provider/model cannot accept audio. For example an Anthropic page can use Anthropic for text/image and Gemini or an OpenAI transcription model for `VOICE_TRANSCRIPTION`.

Provider secrets are synced from the restricted Control Spreadsheet into PostgreSQL. The n8n runtime sends only `accountId`, prompt, and input media to the internal `ai-gateway`; it does not include the provider secret in workflow payloads. Blank secret cells preserve the already stored secret, matching the existing Meta-token behavior.
"""
if '## Dynamic AI provider/model per account' not in docs:
    docs += provider_section
# Add VOICE_TRANSCRIPTION to prompt registry docs if absent.
if '`VOICE_TRANSCRIPTION`' not in docs:
    docs = docs.replace('- `IMAGE_PRODUCT_ANALYSIS`\n', '- `IMAGE_PRODUCT_ANALYSIS`\n- `VOICE_TRANSCRIPTION`\n')
docs_path.write_text(docs, encoding='utf-8')

# Remove outdated instructions that require a fixed OpenAI credential in n8n.
for filename in ['workflows/modular/README.md', 'docs/MODULAR_WORKFLOWS.md', 'docs/IMPLEMENTATION_NOTES.md', 'DOCUMENTATION.md']:
    p = Path(filename)
    if not p.exists():
        continue
    t = p.read_text(encoding='utf-8')
    t = t.replace('Postgres, Google Sheets, and OpenAI credentials', 'Postgres and Google Sheets credentials')
    t = t.replace('Meta/Google/OpenAI end-to-end testing', 'Meta/Google/dynamic-AI-provider end-to-end testing')
    p.write_text(t, encoding='utf-8')

# Optional gateway tuning env vars.
env_path = Path('.env.example')
env = env_path.read_text(encoding='utf-8')
if 'AI_REQUEST_TIMEOUT_MS=' not in env:
    env += "\n# Internal dynamic AI gateway (provider/model/key come from Control Spreadsheet)\nAI_REQUEST_TIMEOUT_MS=120000\nAI_GATEWAY_MAX_BODY_BYTES=41943040\n"
env_path.write_text(env, encoding='utf-8')

# Validate all JSON exports touched by the migration.
for p in Path('workflows/modular').glob('*.json'):
    json.loads(p.read_text(encoding='utf-8'))

print('Dynamic multi-provider AI migration completed successfully')
