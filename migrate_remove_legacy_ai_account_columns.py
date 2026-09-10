import json
import re
from pathlib import Path

LEGACY_HEADERS = {'AI Provider', 'AI Model', 'AI Prompt Override'}
LEGACY_SCHEMA_LINES = [
    "  ai_provider TEXT NOT NULL DEFAULT 'openai',\n",
    "  ai_model TEXT NOT NULL DEFAULT 'gpt-5.6-luna',\n",
    "  ai_prompt_override TEXT NOT NULL DEFAULT '',\n",
]
DROP_SQL = """\n-- Legacy account-level AI fields are obsolete. Runtime AI configuration lives only in 03_AI_PROMPTS / 04_AI_MODELS.\nALTER TABLE business_accounts DROP COLUMN IF EXISTS ai_provider;\nALTER TABLE business_accounts DROP COLUMN IF EXISTS ai_model;\nALTER TABLE business_accounts DROP COLUMN IF EXISTS ai_prompt_override;\n"""


def strip_schema(text: str) -> str:
    for line in LEGACY_SCHEMA_LINES:
        text = text.replace(line, '')
    return text


def transform_strings(value):
    if isinstance(value, dict):
        return {k: transform_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [transform_strings(v) for v in value]
    if isinstance(value, str):
        return strip_schema(value)
    return value


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')


def patch_setup():
    path = Path('workflows/modular/01_SETUP_CONFIG_V4_2.json')
    wf = transform_strings(json.loads(path.read_text(encoding='utf-8')))
    nodes = {n['name']: n for n in wf['nodes']}

    build = nodes['02.05 - Build Missing Control Tabs']['parameters']['jsCode']
    build = build.replace(', "AI Provider", "AI Model", "AI Prompt Override"', '')
    for h in LEGACY_HEADERS:
        assert h not in build, f'{h} still present in setup headers'
    nodes['02.05 - Build Missing Control Tabs']['parameters']['jsCode'] = build

    # Only write header rows for tabs created during this bootstrap. Existing controller sheets
    # are left intact so their data never shifts merely because the install workflow is re-run.
    prep = nodes['02.07 - Prepare Control Header Batch']['parameters']['jsCode']
    old = "const x=$('02.05 - Build Missing Control Tabs').item.json;const data=Object.entries(x.headers).map(([title,row])=>({range:`${title}!A1`,majorDimension:'ROWS',values:[row]}));"
    new = "const x=$('02.05 - Build Missing Control Tabs').item.json;const missing=new Set(Array.isArray(x.missing)?x.missing:[]);const data=Object.entries(x.headers).filter(([title])=>missing.has(title)).map(([title,row])=>({range:`${title}!A1`,majorDimension:'ROWS',values:[row]}));"
    if old in prep:
        prep = prep.replace(old, new)
    elif 'filter(([title])=>missing.has(title))' not in prep:
        raise AssertionError('Unexpected 02.07 header-preparation code')
    nodes['02.07 - Prepare Control Header Batch']['parameters']['jsCode'] = prep

    migrate = nodes['02.02 - Apply / Migrate Database Schema']['parameters']['query']
    if 'DROP COLUMN IF EXISTS ai_provider' not in migrate:
        migrate += DROP_SQL
    nodes['02.02 - Apply / Migrate Database Schema']['parameters']['query'] = migrate

    save_json(path, wf)


def patch_control_sync():
    path = Path('workflows/modular/01B_CONTROL_SYNC_V4_2.json')
    wf = json.loads(path.read_text(encoding='utf-8'))
    nodes = {n['name']: n for n in wf['nodes']}

    # Read through AF for compatibility with older existing controller sheets. The three legacy
    # account AI columns are ignored, while the named rate-limit/follow-up columns still parse.
    parser = nodes['03.06 - Parse + Validate Accounts']['parameters']['jsCode']
    legacy_js = ",ai_provider:String(x['AI Provider']||'openai').trim(),ai_model:String(x['AI Model']||'gpt-5.6-luna').trim(),ai_prompt_override:String(x['AI Prompt Override']||'').trim()"
    if legacy_js in parser:
        parser = parser.replace(legacy_js, '')
    for h in LEGACY_HEADERS:
        assert h not in parser, f'{h} still read by account parser'
    nodes['03.06 - Parse + Validate Accounts']['parameters']['jsCode'] = parser

    query = nodes['03.07 - Upsert Accounts']['parameters']['query']
    query = query.replace('conversation_url_template text,ai_provider text,ai_model text,ai_prompt_override text,max_messages_per_minute int', 'conversation_url_template text,max_messages_per_minute int')
    query = query.replace('conversation_url_template,ai_provider,ai_model,ai_prompt_override,max_messages_per_minute', 'conversation_url_template,max_messages_per_minute')
    query = query.replace('conversation_url_template=EXCLUDED.conversation_url_template,ai_provider=EXCLUDED.ai_provider,ai_model=EXCLUDED.ai_model,ai_prompt_override=EXCLUDED.ai_prompt_override,max_messages_per_minute=EXCLUDED.max_messages_per_minute', 'conversation_url_template=EXCLUDED.conversation_url_template,max_messages_per_minute=EXCLUDED.max_messages_per_minute')
    for token in ('ai_provider', 'ai_model', 'ai_prompt_override'):
        assert token not in query, f'{token} still present in account upsert'
    nodes['03.07 - Upsert Accounts']['parameters']['query'] = query

    save_json(path, wf)


def patch_schema_files():
    init = Path('init-db/001-init.sql')
    text = strip_schema(init.read_text(encoding='utf-8'))
    marker = 'CREATE INDEX IF NOT EXISTS idx_business_accounts_business ON business_accounts(business_id) WHERE active=TRUE;\n'
    if 'DROP COLUMN IF EXISTS ai_provider' not in text:
        text = text.replace(marker, marker + DROP_SQL)
    init.write_text(text, encoding='utf-8')

    for name in ('docs/DATABASE_SCHEMA.sql', 'docs/RESET_APPLICATION_DATABASE.sql'):
        p = Path(name)
        p.write_text(strip_schema(p.read_text(encoding='utf-8')), encoding='utf-8')

    reset = Path('workflows/modular/00_RESET_AGENT_APP_V4_2.json')
    wf = transform_strings(json.loads(reset.read_text(encoding='utf-8')))
    save_json(reset, wf)


def patch_account_docs(pathname: str):
    p = Path(pathname)
    lines = p.read_text(encoding='utf-8').splitlines()
    out = []
    in_accounts = False
    counter = 0
    for line in lines:
        if line.startswith('#'):
            if '02_ACCOUNTS' in line:
                in_accounts = True
                counter = 0
            elif in_accounts:
                in_accounts = False
        if in_accounts:
            m = re.match(r'^(\d+)\.\s+(.*)$', line)
            if m:
                label = m.group(2).strip()
                if label in LEGACY_HEADERS:
                    continue
                counter += 1
                line = f'{counter}. {label}'
        out.append(line)
    text = '\n'.join(out) + '\n'
    if pathname.endswith('CONTROL_SPREADSHEET.md'):
        note = "\n`AI Provider`, `AI Model`, and `AI Prompt Override` are intentionally not part of `02_ACCOUNTS`. Prompts are configured only in `03_AI_PROMPTS`; provider/model/API-key configuration is only in `04_AI_MODELS`. Existing older sheets may still show those legacy columns, but Control Sync ignores them.\n"
        anchor = '## Platform identity rules\n'
        if note.strip() not in text:
            text = text.replace(anchor, note + '\n' + anchor)
    p.write_text(text, encoding='utf-8')


def validate():
    setup = json.loads(Path('workflows/modular/01_SETUP_CONFIG_V4_2.json').read_text(encoding='utf-8'))
    setup_nodes = {n['name']: n for n in setup['nodes']}
    build = setup_nodes['02.05 - Build Missing Control Tabs']['parameters']['jsCode']
    assert all(h not in build for h in LEGACY_HEADERS)
    assert 'filter(([title])=>missing.has(title))' in setup_nodes['02.07 - Prepare Control Header Batch']['parameters']['jsCode']
    assert 'DROP COLUMN IF EXISTS ai_provider' in setup_nodes['02.02 - Apply / Migrate Database Schema']['parameters']['query']

    sync = json.loads(Path('workflows/modular/01B_CONTROL_SYNC_V4_2.json').read_text(encoding='utf-8'))
    sync_nodes = {n['name']: n for n in sync['nodes']}
    parser = sync_nodes['03.06 - Parse + Validate Accounts']['parameters']['jsCode']
    upsert = sync_nodes['03.07 - Upsert Accounts']['parameters']['query']
    assert all(h not in parser for h in LEGACY_HEADERS)
    assert all(x not in upsert for x in ('ai_provider', 'ai_model', 'ai_prompt_override'))

    for p in Path('workflows/modular').glob('*.json'):
        json.loads(p.read_text(encoding='utf-8'))

    control_doc = Path('docs/CONTROL_SPREADSHEET.md').read_text(encoding='utf-8')
    section = control_doc.split('## `02_ACCOUNTS` columns', 1)[1].split('## Platform identity rules', 1)[0]
    numbered_labels = [m.group(1).strip() for m in re.finditer(r'^\d+\.\s+(.*)$', section, flags=re.M)]
    assert not any(label in LEGACY_HEADERS for label in numbered_labels)
    assert '29. Updated At' in section

    schema = Path('init-db/001-init.sql').read_text(encoding='utf-8')
    assert "ai_provider TEXT NOT NULL DEFAULT 'openai'" not in schema
    assert 'DROP COLUMN IF EXISTS ai_provider' in schema
    print('legacy account AI columns removed; validation OK')


patch_setup()
patch_control_sync()
patch_schema_files()
patch_account_docs('docs/CONTROL_SPREADSHEET.md')
patch_account_docs('DOCUMENTATION.md')
validate()
