import json
from pathlib import Path

LEGACY_HEADER = 'Default AI Prompt'
LEGACY_COLUMN = 'ai_instructions'
SCHEMA_LINE = "  ai_instructions TEXT NOT NULL DEFAULT '',\n"
DROP_SQL = """\n-- Legacy business-level prompt storage is obsolete. Runtime prompts live only in 03_AI_PROMPTS.\nALTER TABLE businesses DROP COLUMN IF EXISTS ai_instructions;\n"""


def strip_schema(text: str) -> str:
    return text.replace(SCHEMA_LINE, '')


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
    build = build.replace(', "Default AI Prompt"', '')
    if LEGACY_HEADER in build:
        raise AssertionError('Default AI Prompt still present in 01_BUSINESSES setup headers')
    nodes['02.05 - Build Missing Control Tabs']['parameters']['jsCode'] = build

    migrate = nodes['02.02 - Apply / Migrate Database Schema']['parameters']['query']
    migrate = strip_schema(migrate)
    if 'DROP COLUMN IF EXISTS ai_instructions' not in migrate:
        marker = "CREATE TABLE IF NOT EXISTS ai_prompts ("
        if marker not in migrate:
            raise AssertionError('Could not locate ai_prompts marker in setup schema')
        migrate = migrate.replace(marker, DROP_SQL + '\n' + marker, 1)
    nodes['02.02 - Apply / Migrate Database Schema']['parameters']['query'] = migrate

    save_json(path, wf)


def patch_control_sync():
    path = Path('workflows/modular/01B_CONTROL_SYNC_V4_2.json')
    wf = json.loads(path.read_text(encoding='utf-8'))
    nodes = {n['name']: n for n in wf['nodes']}

    parser = nodes['03.03 - Parse Businesses']['parameters']['jsCode']
    parser = parser.replace(",ai_instructions:String(x['Default AI Prompt']||'')", '')
    if LEGACY_HEADER in parser or LEGACY_COLUMN in parser:
        raise AssertionError('Legacy business prompt still read by Parse Businesses')
    nodes['03.03 - Parse Businesses']['parameters']['jsCode'] = parser

    query = nodes['03.04 - Upsert Businesses']['parameters']['query']
    query = query.replace(',ai_instructions text,active boolean', ',active boolean')
    query = query.replace(',ai_instructions,active,updated_at', ',active,updated_at')
    query = query.replace(',payment_methods,ai_instructions,active,NOW()', ',payment_methods,active,NOW()')
    query = query.replace(',ai_instructions=EXCLUDED.ai_instructions,active=EXCLUDED.active', ',active=EXCLUDED.active')
    if LEGACY_COLUMN in query:
        raise AssertionError('Legacy ai_instructions still present in business upsert query')
    nodes['03.04 - Upsert Businesses']['parameters']['query'] = query

    save_json(path, wf)


def patch_schema_files():
    init = Path('init-db/001-init.sql')
    text = strip_schema(init.read_text(encoding='utf-8'))
    if 'DROP COLUMN IF EXISTS ai_instructions' not in text:
        marker = 'CREATE TABLE IF NOT EXISTS business_accounts ('
        if marker not in text:
            raise AssertionError('business_accounts marker not found in init-db')
        text = text.replace(marker, DROP_SQL + '\n' + marker, 1)
    init.write_text(text, encoding='utf-8')

    for name in ('docs/DATABASE_SCHEMA.sql', 'docs/RESET_APPLICATION_DATABASE.sql'):
        p = Path(name)
        p.write_text(strip_schema(p.read_text(encoding='utf-8')), encoding='utf-8')

    reset = Path('workflows/modular/00_RESET_AGENT_APP_V4_2.json')
    wf = transform_strings(json.loads(reset.read_text(encoding='utf-8')))
    save_json(reset, wf)


def patch_docs():
    for name in ('docs/CONTROL_SPREADSHEET.md', 'DOCUMENTATION.md'):
        p = Path(name)
        text = p.read_text(encoding='utf-8')
        text = text.replace(
            '`Business Key | Business Name | Delivery Charge | Payment Methods | Default AI Prompt | Active | Updated At`',
            '`Business Key | Business Name | Delivery Charge | Payment Methods | Active | Updated At`'
        )
        text = text.replace(
            "`shari_ghor | Shari Ghor | 80 | Cash on Delivery | Reply in the customer's language. Never guess price. | TRUE |`",
            '`shari_ghor | Shari Ghor | 80 | Cash on Delivery | TRUE |`'
        )
        anchor = '`Business Key` is your internal business identifier. It is not a Facebook Page ID.\n'
        note = '\nBusiness-level AI prompt text is intentionally not stored in `01_BUSINESSES`. Configure all runtime prompts per account in `03_AI_PROMPTS`.\n'
        if anchor in text and note.strip() not in text:
            text = text.replace(anchor, anchor + note, 1)
        p.write_text(text, encoding='utf-8')


def validate():
    setup = json.loads(Path('workflows/modular/01_SETUP_CONFIG_V4_2.json').read_text(encoding='utf-8'))
    nodes = {n['name']: n for n in setup['nodes']}
    headers = nodes['02.05 - Build Missing Control Tabs']['parameters']['jsCode']
    assert LEGACY_HEADER not in headers
    assert '"01_BUSINESSES": ["Business Key", "Business Name", "Delivery Charge", "Payment Methods", "Active", "Updated At"]' in headers
    schema = nodes['02.02 - Apply / Migrate Database Schema']['parameters']['query']
    assert SCHEMA_LINE.strip() not in schema
    assert 'DROP COLUMN IF EXISTS ai_instructions' in schema

    sync = json.loads(Path('workflows/modular/01B_CONTROL_SYNC_V4_2.json').read_text(encoding='utf-8'))
    sync_nodes = {n['name']: n for n in sync['nodes']}
    assert LEGACY_HEADER not in sync_nodes['03.03 - Parse Businesses']['parameters']['jsCode']
    assert LEGACY_COLUMN not in sync_nodes['03.04 - Upsert Businesses']['parameters']['query']

    for p in Path('workflows/modular').glob('*.json'):
        json.loads(p.read_text(encoding='utf-8'))

    for name in ('docs/CONTROL_SPREADSHEET.md', 'DOCUMENTATION.md'):
        text = Path(name).read_text(encoding='utf-8')
        assert LEGACY_HEADER not in text
        assert '`Business Key | Business Name | Delivery Charge | Payment Methods | Active | Updated At`' in text

    # Runtime messaging must not depend on the removed business-level prompt field.
    messaging = Path('workflows/modular/05_META_MESSAGING_V4_2.json').read_text(encoding='utf-8')
    assert LEGACY_COLUMN not in messaging

    init = Path('init-db/001-init.sql').read_text(encoding='utf-8')
    assert SCHEMA_LINE.strip() not in init
    assert 'DROP COLUMN IF EXISTS ai_instructions' in init

    print('Default AI Prompt removed from 01_BUSINESSES; runtime prompt source remains 03_AI_PROMPTS; validation OK')


patch_setup()
patch_control_sync()
patch_schema_files()
patch_docs()
validate()
