import json
from pathlib import Path
from uuid import uuid4

WORKFLOW = Path('workflows/modular/05_META_MESSAGING_V4_2.json')
DOCS = Path('docs/CONTROL_SPREADSHEET.md')
PROMPT_KEY = 'IMAGE_PRODUCT_ANALYSIS'
TARGET_NODE = 'Analyze Product Image'
RENDER_NODE = f'Render AI Prompt - {PROMPT_KEY}'
OLD_PROMPT = 'Describe only visible product-identifying details for catalog search. Do NOT guess price, stock, brand or exact product. Return a short search description.'

data = json.loads(WORKFLOW.read_text(encoding='utf-8'))
nodes = data['nodes']
connections = data['connections']
by_name = {n['name']: n for n in nodes}

if TARGET_NODE not in by_name:
    raise SystemExit(f'Missing node: {TARGET_NODE}')

target = by_name[TARGET_NODE]
current_text = str(target.get('parameters', {}).get('text', ''))

renderer_code = r"""const j=$json;
const promptKey='IMAGE_PRODUCT_ANALYSIS';
const registry=(j.aiPrompts&&typeof j.aiPrompts==='object'&&!Array.isArray(j.aiPrompts))?j.aiPrompts:{};
const template=String(registry[promptKey]||'').trim();
if(!template) throw new Error(`Missing active AI prompt ${promptKey} for account ${j.accountId||j.account_id||'unknown'}. Configure it in Control Spreadsheet tab 03_AI_PROMPTS.`);
const getPath=(obj,path)=>{const clean=String(path||'').replace(/^\$json\./,'');return clean.split('.').filter(Boolean).reduce((v,k)=>v==null?undefined:v[k],obj);};
const rendered=template.replace(/\{\{\s*([A-Za-z0-9_.$-]+)\s*\}\}/g,(_,path)=>{const v=getPath(j,path);if(v===undefined||v===null)return '';return typeof v==='object'?JSON.stringify(v):String(v);});
return [{json:{...j,_renderedAiPrompt:rendered,_activePromptKey:promptKey},binary:$binary}];"""

if RENDER_NODE not in by_name:
    pos = target.get('position', [1280, 120])
    renderer = {
        'parameters': {'jsCode': renderer_code},
        'id': str(uuid4()),
        'name': RENDER_NODE,
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [pos[0] - 220, pos[1]],
    }
    nodes.append(renderer)
    by_name[RENDER_NODE] = renderer

    rewired = 0
    for source, branches in connections.items():
        main = branches.get('main') if isinstance(branches, dict) else None
        if not main:
            continue
        for output in main:
            for edge in output:
                if edge.get('node') == TARGET_NODE:
                    edge['node'] = RENDER_NODE
                    rewired += 1
    if rewired == 0:
        raise SystemExit(f'Could not locate a main input connection for {TARGET_NODE}')

    connections[RENDER_NODE] = {
        'main': [[{'node': TARGET_NODE, 'type': 'main', 'index': 0}]]
    }
else:
    by_name[RENDER_NODE]['parameters']['jsCode'] = renderer_code

# n8n contains only the rendered value reference, never prompt content.
target.setdefault('parameters', {})['text'] = '={{ $json._renderedAiPrompt }}'

serialized = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
if OLD_PROMPT in serialized:
    raise SystemExit('Hard-coded image analysis prompt still exists in workflow')
if target['parameters']['text'] != '={{ $json._renderedAiPrompt }}':
    raise SystemExit('Image analysis node is not bound to the external prompt renderer')
if RENDER_NODE not in connections:
    raise SystemExit('Image prompt renderer is not connected')
WORKFLOW.write_text(serialized + '\n', encoding='utf-8')

# Keep the documented active prompt-key registry complete.
docs = DOCS.read_text(encoding='utf-8')
keys = [
    'INTENT_CLASSIFIER',
    'IMAGE_PRODUCT_ANALYSIS',
    'PRODUCT_SEARCH_RESPONSE',
    'ORDER_DETAILS_EXTRACT_AI',
    'GENERAL_ANSWER_AI',
]
marker = 'Current runtime keys are:'
if marker in docs:
    start = docs.index(marker) + len(marker)
    tail = docs[start:]
    # Replace the first contiguous bullet block after the marker.
    lines = tail.splitlines()
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    j = i
    while j < len(lines) and lines[j].lstrip().startswith('- `'):
        j += 1
    new_block = [''] + [f'- `{k}`' for k in keys]
    lines = lines[:i] + new_block + lines[j:]
    docs = docs[:start] + '\n'.join(lines)
else:
    docs += '\n\nCurrent runtime keys are:\n\n' + '\n'.join(f'- `{k}`' for k in keys) + '\n'
DOCS.write_text(docs, encoding='utf-8')

# Final JSON validity check.
json.loads(WORKFLOW.read_text(encoding='utf-8'))
print('Externalized image-analysis AI prompt and updated prompt registry docs.')
