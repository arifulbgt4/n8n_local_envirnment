import json
import re
from pathlib import Path
from uuid import uuid4

RUNTIME_DDL = r'''

-- Account-scoped dynamic AI provider/model registry. Source of truth: Control Spreadsheet 04_AI_MODELS.
CREATE TABLE IF NOT EXISTS ai_runtime_configs (
  id BIGSERIAL PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES business_accounts(id) ON DELETE CASCADE,
  config_key TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  api_key TEXT NOT NULL,
  base_url TEXT NOT NULL DEFAULT '',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  source_updated_at TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(account_id, config_key)
);
CREATE INDEX IF NOT EXISTS idx_ai_runtime_configs_account_active
  ON ai_runtime_configs(account_id, config_key) WHERE active=TRUE;
'''.strip()


def ensure_runtime_ddl(text: str) -> str:
    if 'CREATE TABLE IF NOT EXISTS ai_runtime_configs' in text:
        return text
    return text.rstrip() + '\n\n' + RUNTIME_DDL + '\n'


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')


def nmap(data):
    return {n['name']: n for n in data['nodes']}


def set_main(connections, source, target):
    connections[source] = {'main': [[{'node': target, 'type': 'main', 'index': 0}]]}


def remove_target_edges(connections, target):
    for source, groups in list(connections.items()):
        if not isinstance(groups, dict):
            continue
        for key, outputs in list(groups.items()):
            if not isinstance(outputs, list):
                continue
            new_outputs = []
            for output in outputs:
                if not isinstance(output, list):
                    new_outputs.append(output)
                    continue
                new_outputs.append([edge for edge in output if edge.get('node') != target])
            groups[key] = new_outputs


def http_json_params():
    return {
        'method': 'POST',
        'url': '={{ $json._aiRequest.url }}',
        'sendHeaders': True,
        'specifyHeaders': 'json',
        'jsonHeaders': '={{ JSON.stringify($json._aiRequest.headers) }}',
        'sendBody': True,
        'contentType': 'json',
        'specifyBody': 'json',
        'jsonBody': '={{ JSON.stringify($json._aiRequest.body) }}',
        'options': {},
    }


TEXT_BUILDER_TEMPLATE = r'''const j=$json;
const taskKey='__TASK_KEY__';
const registry=(j.aiRuntimeConfigs&&typeof j.aiRuntimeConfigs==='object'&&!Array.isArray(j.aiRuntimeConfigs))?j.aiRuntimeConfigs:{};
const cfg=registry[taskKey]||registry.DEFAULT;
if(!cfg) throw new Error(`Missing AI runtime config ${taskKey} (or DEFAULT) for account ${j.accountId||'unknown'}. Configure 04_AI_MODELS.`);
const alias={google:'gemini',google_gemini:'gemini','google-gemini':'gemini',claude:'anthropic','openai-compatible':'openai_compatible',openai_compatible:'openai_compatible'};
const rawProvider=String(cfg.provider||'').trim().toLowerCase();
const provider=alias[rawProvider]||rawProvider;
const model=String(cfg.model||'').trim();
const apiKey=String(cfg.apiKey||cfg.api_key||'').trim();
const baseUrl=String(cfg.baseUrl||cfg.base_url||'').trim();
if(!provider||!model||!apiKey) throw new Error(`Incomplete AI runtime config ${taskKey} for account ${j.accountId||'unknown'}: Provider, Model and API Key are required.`);
const trimSlash=s=>String(s||'').replace(/\/+$/,'');
const endpoint=(base,suffix)=>{const b=trimSlash(base);const s=String(suffix||'').replace(/^\/+/, '');return b.toLowerCase().endsWith('/'+s.toLowerCase())?b:`${b}/${s}`;};
const prompt=String(j._renderedAiPrompt||'');
let url='',headers={},body={};
if(provider==='openai'){
  url=endpoint(baseUrl||'https://api.openai.com/v1','chat/completions');
  headers={Authorization:`Bearer ${apiKey}`,'Content-Type':'application/json'};
  body={model,messages:[{role:'user',content:prompt}]};
}else if(provider==='openai_compatible'){
  if(!baseUrl) throw new Error(`AI Base URL is required for openai_compatible on account ${j.accountId||'unknown'}.`);
  url=endpoint(baseUrl,'chat/completions');
  headers={Authorization:`Bearer ${apiKey}`,'Content-Type':'application/json'};
  body={model,messages:[{role:'user',content:prompt}]};
}else if(provider==='anthropic'){
  url=endpoint(baseUrl||'https://api.anthropic.com/v1','messages');
  headers={'x-api-key':apiKey,'anthropic-version':'2023-06-01','Content-Type':'application/json'};
  body={model,max_tokens:2048,messages:[{role:'user',content:prompt}]};
}else if(provider==='gemini'){
  const root=trimSlash(baseUrl||'https://generativelanguage.googleapis.com/v1beta');
  url=root.includes(':generateContent')?root:`${root}/models/${encodeURIComponent(model)}:generateContent`;
  headers={'x-goog-api-key':apiKey,'Content-Type':'application/json'};
  body={contents:[{role:'user',parts:[{text:prompt}]}]};
}else{
  throw new Error(`Unsupported AI provider "${provider}" for account ${j.accountId||'unknown'}. Supported: openai, anthropic, gemini, openai_compatible.`);
}
return [{json:{...j,_aiTaskKey:taskKey,_aiProvider:provider,_aiModel:model,_aiRequest:{url,headers,body}}}];'''


TEXT_NORMALIZER_TEMPLATE = r'''const base=$('__BUILDER_NAME__').item.json;
const r=$json||{};
const provider=base._aiProvider;
let text='';
if(provider==='openai'||provider==='openai_compatible'){
  const c=r.choices?.[0]?.message?.content;
  text=typeof c==='string'?c:Array.isArray(c)?c.map(x=>x?.text||x?.content||'').join(''):'';
}else if(provider==='anthropic'){
  text=Array.isArray(r.content)?r.content.map(x=>x?.text||'').join(''):String(r.content||'');
}else if(provider==='gemini'){
  text=(r.candidates?.[0]?.content?.parts||[]).map(x=>x?.text||'').join('');
}
if(!String(text||'').trim()){
  const err=r.error?.message||r.message||'';
  throw new Error(`AI provider ${provider} returned no text${err?`: ${err}`:''}`);
}
const clean={...base};delete clean._aiRequest;delete clean.aiRuntimeConfigs;
return [{json:{...clean,output:String(text),text:String(text),content:String(text),aiProvider:provider,aiModel:base._aiModel}}];'''


IMAGE_BUILDER = r'''const j=$json;
const taskKey='IMAGE_PRODUCT_ANALYSIS';
const registry=(j.aiRuntimeConfigs&&typeof j.aiRuntimeConfigs==='object'&&!Array.isArray(j.aiRuntimeConfigs))?j.aiRuntimeConfigs:{};
const cfg=registry[taskKey]||registry.DEFAULT;
if(!cfg) throw new Error(`Missing AI runtime config ${taskKey} (or DEFAULT) for account ${j.accountId||'unknown'}. Configure 04_AI_MODELS.`);
const alias={google:'gemini',google_gemini:'gemini','google-gemini':'gemini',claude:'anthropic','openai-compatible':'openai_compatible',openai_compatible:'openai_compatible'};
const rawProvider=String(cfg.provider||'').trim().toLowerCase();const provider=alias[rawProvider]||rawProvider;
const model=String(cfg.model||'').trim();const apiKey=String(cfg.apiKey||cfg.api_key||'').trim();const baseUrl=String(cfg.baseUrl||cfg.base_url||'').trim();
if(!provider||!model||!apiKey) throw new Error(`Incomplete AI runtime config ${taskKey}: Provider, Model and API Key are required.`);
const input=$input.first();const buffer=await this.helpers.getBinaryDataBuffer(0,'data');const mime=input.binary?.data?.mimeType||'image/jpeg';const b64=buffer.toString('base64');
const trimSlash=s=>String(s||'').replace(/\/+$/,'');const endpoint=(base,suffix)=>{const b=trimSlash(base);const s=String(suffix||'').replace(/^\/+/, '');return b.toLowerCase().endsWith('/'+s.toLowerCase())?b:`${b}/${s}`;};
const prompt=String(j._renderedAiPrompt||'');let url='',headers={},body={};
if(provider==='openai'||provider==='openai_compatible'){
  const root=provider==='openai'?(baseUrl||'https://api.openai.com/v1'):baseUrl;if(!root)throw new Error('AI Base URL is required for openai_compatible.');
  url=endpoint(root,'chat/completions');headers={Authorization:`Bearer ${apiKey}`,'Content-Type':'application/json'};
  body={model,messages:[{role:'user',content:[{type:'text',text:prompt},{type:'image_url',image_url:{url:`data:${mime};base64,${b64}`}}]}]};
}else if(provider==='anthropic'){
  url=endpoint(baseUrl||'https://api.anthropic.com/v1','messages');headers={'x-api-key':apiKey,'anthropic-version':'2023-06-01','Content-Type':'application/json'};
  body={model,max_tokens:2048,messages:[{role:'user',content:[{type:'image',source:{type:'base64',media_type:mime,data:b64}},{type:'text',text:prompt}]}]};
}else if(provider==='gemini'){
  const root=trimSlash(baseUrl||'https://generativelanguage.googleapis.com/v1beta');url=root.includes(':generateContent')?root:`${root}/models/${encodeURIComponent(model)}:generateContent`;
  headers={'x-goog-api-key':apiKey,'Content-Type':'application/json'};body={contents:[{role:'user',parts:[{text:prompt},{inlineData:{mimeType:mime,data:b64}}]}]};
}else throw new Error(`Unsupported AI provider "${provider}" for image analysis.`);
return [{json:{...j,_aiTaskKey:taskKey,_aiProvider:provider,_aiModel:model,_aiRequest:{url,headers,body}},binary:input.binary}];'''


AUDIO_RENDERER = r'''const j=$json;
const promptKey='AUDIO_TRANSCRIPTION';
const registry=(j.aiPrompts&&typeof j.aiPrompts==='object'&&!Array.isArray(j.aiPrompts))?j.aiPrompts:{};
const template=String(registry[promptKey]||'').trim();
if(!template) throw new Error(`Missing active AI prompt ${promptKey} for account ${j.accountId||'unknown'}. Configure it in Control Spreadsheet tab 03_AI_PROMPTS.`);
const getPath=(obj,path)=>{const clean=String(path||'').replace(/^\$json\./,'');return clean.split('.').filter(Boolean).reduce((v,k)=>v==null?undefined:v[k],obj);};
const rendered=template.replace(/\{\{\s*([A-Za-z0-9_.$-]+)\s*\}\}/g,(_,path)=>{const v=getPath(j,path);if(v===undefined||v===null)return '';return typeof v==='object'?JSON.stringify(v):String(v);});
return [{json:{...j,_renderedAiPrompt:rendered,_activePromptKey:promptKey},binary:$input.first().binary}];'''


AUDIO_BUILDER = r'''const j=$json;const taskKey='AUDIO_TRANSCRIPTION';
const registry=(j.aiRuntimeConfigs&&typeof j.aiRuntimeConfigs==='object'&&!Array.isArray(j.aiRuntimeConfigs))?j.aiRuntimeConfigs:{};const cfg=registry[taskKey]||registry.DEFAULT;
if(!cfg) throw new Error(`Missing AI runtime config ${taskKey} (or DEFAULT) for account ${j.accountId||'unknown'}. Configure 04_AI_MODELS.`);
const alias={google:'gemini',google_gemini:'gemini','google-gemini':'gemini',claude:'anthropic','openai-compatible':'openai_compatible',openai_compatible:'openai_compatible'};const rawProvider=String(cfg.provider||'').trim().toLowerCase();const provider=alias[rawProvider]||rawProvider;
const model=String(cfg.model||'').trim();const apiKey=String(cfg.apiKey||cfg.api_key||'').trim();const baseUrl=String(cfg.baseUrl||cfg.base_url||'').trim();if(!provider||!model||!apiKey)throw new Error(`Incomplete AI runtime config ${taskKey}: Provider, Model and API Key are required.`);
if(provider==='anthropic') throw new Error('Anthropic runtime adapter does not support audio transcription. Add an AUDIO_TRANSCRIPTION override in 04_AI_MODELS using gemini, openai, or openai_compatible.');
const input=$input.first();const trimSlash=s=>String(s||'').replace(/\/+$/,'');const endpoint=(base,suffix)=>{const b=trimSlash(base);const s=String(suffix||'').replace(/^\/+/, '');return b.toLowerCase().endsWith('/'+s.toLowerCase())?b:`${b}/${s}`;};let url='',headers={},body=null,transport='';
if(provider==='openai'||provider==='openai_compatible'){
  const root=provider==='openai'?(baseUrl||'https://api.openai.com/v1'):baseUrl;if(!root)throw new Error('AI Base URL is required for openai_compatible.');url=endpoint(root,'audio/transcriptions');headers={Authorization:`Bearer ${apiKey}`};transport='multipart';
}else if(provider==='gemini'){
  const buffer=await this.helpers.getBinaryDataBuffer(0,'data');const mime=input.binary?.data?.mimeType||'audio/mpeg';const b64=buffer.toString('base64');const root=trimSlash(baseUrl||'https://generativelanguage.googleapis.com/v1beta');url=root.includes(':generateContent')?root:`${root}/models/${encodeURIComponent(model)}:generateContent`;headers={'x-goog-api-key':apiKey,'Content-Type':'application/json'};body={contents:[{role:'user',parts:[{text:String(j._renderedAiPrompt||'')},{inlineData:{mimeType:mime,data:b64}}]}]};transport='json';
}else throw new Error(`Unsupported AI provider "${provider}" for audio transcription.`);
return [{json:{...j,_aiTaskKey:taskKey,_aiProvider:provider,_aiModel:model,_aiTransport:transport,_aiRequest:{url,headers,body}},binary:input.binary}];'''


AUDIO_NORMALIZER = r'''const base=$('Build Dynamic Audio AI Request').item.json;const r=$json||{};const provider=base._aiProvider;let text='';
if(provider==='openai'||provider==='openai_compatible') text=String(r.text||r.transcription||'');
else if(provider==='gemini') text=(r.candidates?.[0]?.content?.parts||[]).map(x=>x?.text||'').join('');
if(!text.trim()){const err=r.error?.message||r.message||'';throw new Error(`Audio provider ${provider} returned no transcript${err?`: ${err}`:''}`);}
const clean={...base};delete clean._aiRequest;delete clean.aiRuntimeConfigs;return [{json:{...clean,text,transcription:text,content:text,output:text,aiProvider:provider,aiModel:base._aiModel}}];'''


# 1) Database schema files.
for file_name in ['init-db/001-init.sql','docs/DATABASE_SCHEMA.sql','docs/RESET_APPLICATION_DATABASE.sql']:
    p=Path(file_name)
    p.write_text(ensure_runtime_ddl(p.read_text(encoding='utf-8')),encoding='utf-8')

# 2) Setup workflow: DB migration + Control Spreadsheet tab.
setup_path=Path('workflows/modular/01_SETUP_CONFIG_V4_2.json')
setup=json.loads(setup_path.read_text(encoding='utf-8'))
setup_nodes=nmap(setup)
schema=setup_nodes['02.02 - Apply / Migrate Database Schema']
schema['parameters']['query']=ensure_runtime_ddl(schema['parameters']['query'])
control=setup_nodes['02.05 - Build Missing Control Tabs']
code=control['parameters']['jsCode']
if '04_AI_MODELS' not in code:
    marker=', "05_SYNC_STATUS": ["Account Key", "Status", "Message", "Last Sync At"]'
    addition=', "04_AI_MODELS": ["Account Key", "Config Key", "Provider", "Model", "API Key", "Base URL", "Active", "Updated At", "Notes"]'+marker
    if marker not in code:
        raise RuntimeError('Could not insert 04_AI_MODELS tab into setup workflow')
    control['parameters']['jsCode']=code.replace(marker,addition,1)
save_json(setup_path,setup)

# 3) Control sync: 04_AI_MODELS -> PostgreSQL.
sync_path=Path('workflows/modular/01B_CONTROL_SYNC_V4_2.json')
sync=json.loads(sync_path.read_text(encoding='utf-8'))
sync_nodes=sync['nodes']; sync_map=nmap(sync); sync_conn=sync['connections']
if '03.11 - Read AI Models' not in sync_map:
    read_node={
      'parameters':{'url':"={{ 'https://sheets.googleapis.com/v4/spreadsheets/' + $('03.01 - Load Control Spreadsheet ID').item.json.control_spreadsheet_id + '/values/' + encodeURIComponent('04_AI_MODELS!A:I') }}",'authentication':'predefinedCredentialType','nodeCredentialType':'googleSheetsOAuth2Api','options':{}},
      'id':str(uuid4()),'name':'03.11 - Read AI Models','type':'n8n-nodes-base.httpRequest','typeVersion':4.2,'position':[-380,-100],'continueOnFail':True
    }
    parse_code=r'''const v=$json.values||[];if($json.error)return[];if(v.length<1)return[{json:{rows:[]}}];const h=v[0];const bool=(x,d=true)=>x===''||x===null||x===undefined?d:!['false','0','no','off','inactive','disabled'].includes(String(x).trim().toLowerCase());const normProvider=x=>{const s=String(x||'').trim().toLowerCase();const m={google:'gemini',google_gemini:'gemini','google-gemini':'gemini',claude:'anthropic','openai-compatible':'openai_compatible'};return m[s]||s;};const rows=v.slice(1).map(r=>Object.fromEntries(h.map((k,i)=>[String(k||'').trim(),r[i]??'']))).map(x=>({account_key:String(x['Account Key']||'').trim(),config_key:String(x['Config Key']||'DEFAULT').trim().toUpperCase().replace(/[^A-Z0-9]+/g,'_').replace(/^_|_$/g,''),provider:normProvider(x['Provider']),model:String(x['Model']||'').trim(),api_key:String(x['API Key']||''),base_url:String(x['Base URL']||'').trim(),active:bool(x['Active'],true),source_updated_at:String(x['Updated At']||'').trim()})).filter(x=>x.account_key&&x.config_key&&x.provider&&x.model&&(!x.active||x.api_key.trim()));return[{json:{rows}}];'''
    parse_node={'parameters':{'jsCode':parse_code},'id':str(uuid4()),'name':'03.12 - Parse + Validate AI Models','type':'n8n-nodes-base.code','typeVersion':2,'position':[-140,-100]}
    upsert_query=RUNTIME_DDL+r'''

WITH incoming AS (
  SELECT * FROM jsonb_to_recordset($1::jsonb)
    AS x(account_key text,config_key text,provider text,model text,api_key text,base_url text,active boolean,source_updated_at text)
), resolved AS (
  SELECT ba.id AS account_id,i.config_key,i.provider,i.model,i.api_key,COALESCE(i.base_url,'') AS base_url,COALESCE(i.active,TRUE) AS active,i.source_updated_at
  FROM incoming i JOIN business_accounts ba ON ba.account_key=i.account_key
), deactivated AS (
  UPDATE ai_runtime_configs c SET active=FALSE,updated_at=NOW()
  WHERE c.active=TRUE AND NOT EXISTS (
    SELECT 1 FROM resolved r WHERE r.account_id=c.account_id AND r.config_key=c.config_key
  ) RETURNING c.account_id
), upserted AS (
  INSERT INTO ai_runtime_configs(account_id,config_key,provider,model,api_key,base_url,active,source_updated_at,updated_at)
  SELECT account_id,config_key,provider,model,api_key,base_url,active,source_updated_at,NOW() FROM resolved
  ON CONFLICT(account_id,config_key) DO UPDATE SET
    provider=EXCLUDED.provider,model=EXCLUDED.model,api_key=EXCLUDED.api_key,base_url=EXCLUDED.base_url,
    active=EXCLUDED.active,source_updated_at=EXCLUDED.source_updated_at,updated_at=NOW()
  WHERE ai_runtime_configs.provider IS DISTINCT FROM EXCLUDED.provider
     OR ai_runtime_configs.model IS DISTINCT FROM EXCLUDED.model
     OR ai_runtime_configs.api_key IS DISTINCT FROM EXCLUDED.api_key
     OR ai_runtime_configs.base_url IS DISTINCT FROM EXCLUDED.base_url
     OR ai_runtime_configs.active IS DISTINCT FROM EXCLUDED.active
     OR ai_runtime_configs.source_updated_at IS DISTINCT FROM EXCLUDED.source_updated_at
  RETURNING ai_runtime_configs.account_id
), changed AS (
  SELECT account_id FROM deactivated UNION SELECT account_id FROM upserted
), cache_deleted AS (
  DELETE FROM response_cache rc WHERE rc.account_id IN (SELECT account_id FROM changed) RETURNING rc.id
)
SELECT (SELECT COUNT(*) FROM resolved)::int AS valid_model_rows,
       ((SELECT COUNT(*) FROM incoming)-(SELECT COUNT(*) FROM resolved))::int AS unmatched_model_rows,
       (SELECT COUNT(*) FROM changed)::int AS changed_accounts,
       (SELECT COUNT(*) FROM cache_deleted)::int AS invalidated_cache_rows;
'''
    upsert_node={'parameters':{'operation':'executeQuery','query':upsert_query,'options':{'queryReplacement':'={{ [JSON.stringify($json.rows||[])] }}'}},'id':str(uuid4()),'name':'03.13 - Sync AI Models to Database','type':'n8n-nodes-base.postgres','typeVersion':2.6,'position':[100,-100]}
    sync_nodes.extend([read_node,parse_node,upsert_node])
    set_main(sync_conn,'03.10 - Sync AI Prompts to Database','03.11 - Read AI Models')
    set_main(sync_conn,'03.11 - Read AI Models','03.12 - Parse + Validate AI Models')
    set_main(sync_conn,'03.12 - Parse + Validate AI Models','03.13 - Sync AI Models to Database')
save_json(sync_path,sync)

# 4) Messaging workflow: provider-neutral HTTP adapters.
msg_path=Path('workflows/modular/05_META_MESSAGING_V4_2.json')
msg=json.loads(msg_path.read_text(encoding='utf-8'))
msg_nodes=msg['nodes']; msg_conn=msg['connections']; by=nmap(msg)
load=by['Load Business + Customer + Conversation']
q=load['parameters']['query']
if ' AS ai_runtime_configs' not in q:
    needle="COALESCE((SELECT jsonb_object_agg(ap.prompt_key,ap.prompt_text) FROM ai_prompts ap WHERE ap.account_id=acct.id AND ap.active=TRUE),'{}'::jsonb) AS ai_prompts,"
    if needle not in q: raise RuntimeError('Could not locate ai_prompts aggregate in messaging query')
    addition=needle+"\n COALESCE((SELECT jsonb_object_agg(c.config_key,jsonb_build_object('provider',c.provider,'model',c.model,'apiKey',c.api_key,'baseUrl',c.base_url)) FROM ai_runtime_configs c WHERE c.account_id=acct.id AND c.active=TRUE),'{}'::jsonb) AS ai_runtime_configs,"
    q=q.replace(needle,addition,1)
q=q.replace('acct.ai_provider,acct.ai_model,','')
load['parameters']['query']=q

base=by['Build Base Context']; bcode=base['parameters']['jsCode']
old="aiPrompts:j.ai_prompts||{},aiProvider:j.ai_provider||'openai',aiModel:j.ai_model||'gpt-5.6-luna',"
if old in bcode:
    bcode=bcode.replace(old,"aiPrompts:j.ai_prompts||{},aiRuntimeConfigs:j.ai_runtime_configs||{},",1)
elif 'aiRuntimeConfigs:j.ai_runtime_configs' not in bcode:
    bcode=bcode.replace('aiPrompts:j.ai_prompts||{},','aiPrompts:j.ai_prompts||{},aiRuntimeConfigs:j.ai_runtime_configs||{},',1)
    bcode=re.sub(r"aiProvider:j\.ai_provider\|\|[^,]+,aiModel:j\.ai_model\|\|[^,]+,",'',bcode)
base['parameters']['jsCode']=bcode

# Remove fixed OpenAI language-model node and its special connection.
msg_nodes[:]=[n for n in msg_nodes if n.get('name')!='OpenAI Chat Model - Core']
msg_conn.pop('OpenAI Chat Model - Core',None)
remove_target_edges(msg_conn,'OpenAI Chat Model - Core')
by=nmap(msg)


def add_text_adapter(task_key, ai_name, downstream):
    renderer=f'Render AI Prompt - {task_key}'
    if renderer not in by or ai_name not in by or downstream not in by:
        raise RuntimeError(f'Missing text AI chain for {task_key}')
    ai=by[ai_name]; pos=ai.get('position',[0,0]); builder_name=f'Build Dynamic AI Request - {task_key}'; norm_name=f'Normalize Dynamic AI Response - {task_key}'
    if builder_name not in by:
        builder={'parameters':{'jsCode':TEXT_BUILDER_TEMPLATE.replace('__TASK_KEY__',task_key)},'id':str(uuid4()),'name':builder_name,'type':'n8n-nodes-base.code','typeVersion':2,'position':[pos[0]-180,pos[1]]}
        norm={'parameters':{'jsCode':TEXT_NORMALIZER_TEMPLATE.replace('__BUILDER_NAME__',builder_name)},'id':str(uuid4()),'name':norm_name,'type':'n8n-nodes-base.code','typeVersion':2,'position':[pos[0]+180,pos[1]]}
        msg_nodes.extend([builder,norm]);by[builder_name]=builder;by[norm_name]=norm
    ai['type']='n8n-nodes-base.httpRequest';ai['typeVersion']=4.2;ai['parameters']=http_json_params();ai.pop('credentials',None)
    set_main(msg_conn,renderer,builder_name);set_main(msg_conn,builder_name,ai_name);set_main(msg_conn,ai_name,norm_name);set_main(msg_conn,norm_name,downstream)


add_text_adapter('INTENT_CLASSIFIER','AI Intent Classifier','Parse AI Intent')
add_text_adapter('PRODUCT_SEARCH_RESPONSE','Product Answer AI','Parse Product Answer')
add_text_adapter('ORDER_DETAILS_EXTRACT_AI','Order Details Extract AI','Parse Order Details')
add_text_adapter('GENERAL_ANSWER_AI','General Answer AI','Parse General Answer')
by=nmap(msg)

# Image adapter.
image_renderer='Render AI Prompt - IMAGE_PRODUCT_ANALYSIS'; image_ai='Analyze Product Image'; image_down='Attach Image Analysis'
if image_renderer not in by or image_ai not in by: raise RuntimeError('Missing image AI chain')
ai=by[image_ai];pos=ai.get('position',[0,0]);ib='Build Dynamic Image AI Request';inn='Normalize Dynamic Image AI Response'
if ib not in by:
    bn={'parameters':{'jsCode':IMAGE_BUILDER},'id':str(uuid4()),'name':ib,'type':'n8n-nodes-base.code','typeVersion':2,'position':[pos[0]-180,pos[1]]}
    nn={'parameters':{'jsCode':TEXT_NORMALIZER_TEMPLATE.replace('__BUILDER_NAME__',ib)},'id':str(uuid4()),'name':inn,'type':'n8n-nodes-base.code','typeVersion':2,'position':[pos[0]+180,pos[1]]}
    msg_nodes.extend([bn,nn]);by[ib]=bn;by[inn]=nn
ai['type']='n8n-nodes-base.httpRequest';ai['typeVersion']=4.2;ai['parameters']=http_json_params();ai.pop('credentials',None)
set_main(msg_conn,image_renderer,ib);set_main(msg_conn,ib,image_ai);set_main(msg_conn,image_ai,inn);set_main(msg_conn,inn,image_down)

# Audio adapter: prompt + provider/model/key are dynamic too.
old_audio=by.get('Transcribe Voice');audio_pos=old_audio.get('position',[1280,280]) if old_audio else [1280,280]
if old_audio:
    msg_nodes[:]=[n for n in msg_nodes if n.get('name')!='Transcribe Voice'];msg_conn.pop('Transcribe Voice',None);remove_target_edges(msg_conn,'Transcribe Voice')
by=nmap(msg)
audio_nodes=[]
def new_code(name,code,pos): return {'parameters':{'jsCode':code},'id':str(uuid4()),'name':name,'type':'n8n-nodes-base.code','typeVersion':2,'position':pos}
if 'Render AI Prompt - AUDIO_TRANSCRIPTION' not in by:
    audio_nodes.append(new_code('Render AI Prompt - AUDIO_TRANSCRIPTION',AUDIO_RENDERER,[audio_pos[0]-360,audio_pos[1]]))
    audio_nodes.append(new_code('Build Dynamic Audio AI Request',AUDIO_BUILDER,[audio_pos[0]-180,audio_pos[1]]))
    audio_nodes.append(new_code('Route Dynamic Audio Multipart',"return $input.all().filter(i=>i.json._aiTransport==='multipart');",[audio_pos[0],audio_pos[1]-60]))
    audio_nodes.append(new_code('Route Dynamic Audio JSON',"return $input.all().filter(i=>i.json._aiTransport==='json');",[audio_pos[0],audio_pos[1]+80]))
    multipart={'parameters':{'method':'POST','url':'={{ $json._aiRequest.url }}','sendHeaders':True,'specifyHeaders':'json','jsonHeaders':'={{ JSON.stringify($json._aiRequest.headers) }}','sendBody':True,'contentType':'multipart-form-data','bodyParameters':{'parameters':[{'name':'model','value':'={{ $json._aiModel }}'},{'parameterType':'formBinaryData','name':'file','inputDataFieldName':'data'},{'name':'prompt','value':'={{ $json._renderedAiPrompt }}'}]},'options':{}},'id':str(uuid4()),'name':'Dynamic Audio AI HTTP - Multipart','type':'n8n-nodes-base.httpRequest','typeVersion':4.2,'position':[audio_pos[0]+200,audio_pos[1]-60]}
    jsonhttp={'parameters':http_json_params(),'id':str(uuid4()),'name':'Dynamic Audio AI HTTP - JSON','type':'n8n-nodes-base.httpRequest','typeVersion':4.2,'position':[audio_pos[0]+200,audio_pos[1]+80]}
    normal=new_code('Normalize Dynamic Audio AI Response',AUDIO_NORMALIZER,[audio_pos[0]+420,audio_pos[1]])
    audio_nodes.extend([multipart,jsonhttp,normal]);msg_nodes.extend(audio_nodes)
by=nmap(msg)
set_main(msg_conn,'Only Audio Binary','Render AI Prompt - AUDIO_TRANSCRIPTION')
set_main(msg_conn,'Render AI Prompt - AUDIO_TRANSCRIPTION','Build Dynamic Audio AI Request')
msg_conn['Build Dynamic Audio AI Request']={'main':[[{'node':'Route Dynamic Audio Multipart','type':'main','index':0},{'node':'Route Dynamic Audio JSON','type':'main','index':0}]]}
set_main(msg_conn,'Route Dynamic Audio Multipart','Dynamic Audio AI HTTP - Multipart');set_main(msg_conn,'Route Dynamic Audio JSON','Dynamic Audio AI HTTP - JSON')
set_main(msg_conn,'Dynamic Audio AI HTTP - Multipart','Normalize Dynamic Audio AI Response');set_main(msg_conn,'Dynamic Audio AI HTTP - JSON','Normalize Dynamic Audio AI Response');set_main(msg_conn,'Normalize Dynamic Audio AI Response','Attach Voice Transcript')

# Ensure old vendor-specific LangChain AI nodes are gone.
for n in msg_nodes:
    t=str(n.get('type','')).lower()
    if 'openai' in t or 'lmchatopenai' in t:
        raise RuntimeError(f'Vendor-specific OpenAI n8n node still exists: {n.get("name")} / {n.get("type")}')

# Prompt registry must include audio prompt as an external prompt; no n8n prompt content is seeded.
save_json(msg_path,msg)

# 5) Documentation.
docs_path=Path('docs/CONTROL_SPREADSHEET.md');docs=docs_path.read_text(encoding='utf-8')
if '- `04_AI_MODELS`' not in docs:
    docs=docs.replace('- `03_AI_PROMPTS`\n- `05_SYNC_STATUS`','- `03_AI_PROMPTS`\n- `04_AI_MODELS`\n- `05_SYNC_STATUS`')
if '- `AUDIO_TRANSCRIPTION`' not in docs:
    docs=docs.replace('- `IMAGE_PRODUCT_ANALYSIS`\n','- `IMAGE_PRODUCT_ANALYSIS`\n- `AUDIO_TRANSCRIPTION`\n')
section=r'''

## 04_AI_MODELS — account-scoped provider/model/API-key registry

All AI provider, model and API-key selection is controlled from this tab. There is no fixed OpenAI/Gemini/Anthropic credential or model fallback inside n8n.

Columns:

`Account Key | Config Key | Provider | Model | API Key | Base URL | Active | Updated At | Notes`

`Config Key=DEFAULT` is an optional account-local default. A task-specific row overrides it. Supported task keys are the prompt keys (`INTENT_CLASSIFIER`, `PRODUCT_SEARCH_RESPONSE`, `ORDER_DETAILS_EXTRACT_AI`, `GENERAL_ANSWER_AI`, `IMAGE_PRODUCT_ANALYSIS`, `AUDIO_TRANSCRIPTION`).

Supported provider adapters: `openai`, `anthropic`, `gemini`, and `openai_compatible`. `openai_compatible` requires `Base URL`. Provider aliases such as `google`/`google_gemini` and `claude` are normalized during sync.

Example: one Page can use `DEFAULT=anthropic`, `IMAGE_PRODUCT_ANALYSIS=gemini`, and `AUDIO_TRANSCRIPTION=openai`; another Page can use a completely different set. If neither an exact task config nor `DEFAULT` exists, the AI call fails with a configuration error instead of silently falling back to any n8n provider/model.

API keys are intentionally sourced from the Control Spreadsheet as requested and are copied into PostgreSQL by `01B Control Spreadsheet Sync`. Restrict the Control Spreadsheet, PostgreSQL database, and n8n execution-data access to trusted administrators because these are secrets.
'''
if '## 04_AI_MODELS — account-scoped provider/model/API-key registry' not in docs: docs+=section
docs_path.write_text(docs,encoding='utf-8')

# Update modular docs that still require an OpenAI n8n credential.
for file_name in ['workflows/modular/README.md','docs/MODULAR_WORKFLOWS.md','docs/INSTALLATION.md','DOCUMENTATION.md']:
    p=Path(file_name)
    if not p.exists(): continue
    s=p.read_text(encoding='utf-8')
    s=s.replace('Postgres, Google Sheets, and OpenAI credentials','Postgres and Google Sheets credentials; AI provider API keys come from Control Spreadsheet `04_AI_MODELS`')
    s=s.replace('POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY`, and `OPENAI_API_KEY`','POSTGRES_PASSWORD` and `N8N_ENCRYPTION_KEY`')
    p.write_text(s,encoding='utf-8')

# Remove obsolete env-only OpenAI key example if present; runtime does not use it.
env=Path('.env.example')
if env.exists():
    lines=env.read_text(encoding='utf-8').splitlines()
    lines=[ln for ln in lines if not ln.startswith('OPENAI_API_KEY=') and 'Runtime uses this key for OpenAI HTTP calls' not in ln]
    env.write_text('\n'.join(lines).rstrip()+'\n',encoding='utf-8')

# 6) Validation.
for p in [setup_path,sync_path,msg_path]: json.loads(p.read_text(encoding='utf-8'))
serialized=msg_path.read_text(encoding='utf-8')
for forbidden in ['@n8n/n8n-nodes-langchain.openAi','lmChatOpenAi','OpenAI Chat Model - Core','"value":"gpt-5.6-luna"']:
    if forbidden in serialized: raise RuntimeError(f'Fixed OpenAI/model artifact remains in messaging workflow: {forbidden}')
for required in ['ai_runtime_configs','04_AI_MODELS','Build Dynamic AI Request - INTENT_CLASSIFIER','Build Dynamic Image AI Request','Build Dynamic Audio AI Request']:
    if required not in (serialized+sync_path.read_text(encoding='utf-8')+setup_path.read_text(encoding='utf-8')): raise RuntimeError(f'Missing dynamic AI artifact: {required}')
print('Dynamic multi-provider AI runtime migration completed successfully')
