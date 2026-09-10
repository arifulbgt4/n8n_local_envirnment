import json
from pathlib import Path

p = Path('workflows/modular/01_SETUP_CONFIG_V4_2.json')
wf = json.loads(p.read_text(encoding='utf-8'))
nodes = {n['name']: n for n in wf['nodes']}
con = wf['connections']

nodes['02.06 - Create Missing Control Tabs']['continueOnFail'] = True

names = {
    '02.05B - Prepare Control Tab Create Attempt',
    '02.06A - Verify Control Tabs After Create',
    '02.06B - Rebuild Remaining Control Tabs',
    '02.06C - All Control Tabs Ready?',
}
wf['nodes'] = [n for n in wf['nodes'] if n['name'] not in names]
for name in names:
    con.pop(name, None)

wf['nodes'] += [
    {
        'parameters': {
            'jsCode': "const j=$json;\nconst createAttempt=Number(j.createAttempt||0)+1;\nif(createAttempt>3) throw new Error('CONTROL TAB CREATE FAILED: tabs are still missing after 3 verified attempts. Check Docker/network connectivity to sheets.googleapis.com.');\nreturn [{json:{...j,createAttempt}}];"
        },
        'id': '0205b000-0000-4000-8000-000000000001',
        'name': '02.05B - Prepare Control Tab Create Attempt',
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [-1600, -1020],
    },
    {
        'parameters': {
            'url': "={{ 'https://sheets.googleapis.com/v4/spreadsheets/' + $('02.05B - Prepare Control Tab Create Attempt').item.json.controlSpreadsheetId + '?fields=sheets.properties' }}",
            'authentication': 'predefinedCredentialType',
            'nodeCredentialType': 'googleSheetsOAuth2Api',
            'options': {'timeout': 30000},
        },
        'id': '0206a000-0000-4000-8000-000000000001',
        'name': '02.06A - Verify Control Tabs After Create',
        'type': 'n8n-nodes-base.httpRequest',
        'typeVersion': 4.2,
        'position': [-1360, -1020],
        'retryOnFail': True,
        'maxTries': 3,
        'waitBetweenTries': 1500,
    },
    {
        'parameters': {
            'jsCode': "const ctx=$('02.05B - Prepare Control Tab Create Attempt').item.json;\nconst existing=new Set(($json.sheets||[]).map(s=>s.properties?.title).filter(Boolean));\nconst required=ctx.headers||{};\nconst missing=Object.keys(required).filter(t=>!existing.has(t));\nreturn [{json:{...ctx,missing,requests:missing.map(title=>({addSheet:{properties:{title}}})),controlTabsReady:missing.length===0}}];"
        },
        'id': '0206b000-0000-4000-8000-000000000001',
        'name': '02.06B - Rebuild Remaining Control Tabs',
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [-1120, -1020],
    },
    {
        'parameters': {
            'conditions': {
                'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict'},
                'conditions': [
                    {
                        'id': '0206c000-0000-4000-8000-000000000001',
                        'leftValue': '={{ $json.controlTabsReady === true }}',
                        'rightValue': True,
                        'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True},
                    }
                ],
                'combinator': 'and',
            },
            'options': {},
        },
        'id': '0206c000-0000-4000-8000-000000000001',
        'name': '02.06C - All Control Tabs Ready?',
        'type': 'n8n-nodes-base.if',
        'typeVersion': 2.2,
        'position': [-880, -1020],
    },
]

con['02.05A - Any Missing Control Tabs?'] = {
    'main': [
        [{'node': '02.05B - Prepare Control Tab Create Attempt', 'type': 'main', 'index': 0}],
        [{'node': '02.07 - Prepare Control Header Batch', 'type': 'main', 'index': 0}],
    ]
}
con['02.05B - Prepare Control Tab Create Attempt'] = {
    'main': [[{'node': '02.06 - Create Missing Control Tabs', 'type': 'main', 'index': 0}]]
}
con['02.06 - Create Missing Control Tabs'] = {
    'main': [[{'node': '02.06A - Verify Control Tabs After Create', 'type': 'main', 'index': 0}]]
}
con['02.06A - Verify Control Tabs After Create'] = {
    'main': [[{'node': '02.06B - Rebuild Remaining Control Tabs', 'type': 'main', 'index': 0}]]
}
con['02.06B - Rebuild Remaining Control Tabs'] = {
    'main': [[{'node': '02.06C - All Control Tabs Ready?', 'type': 'main', 'index': 0}]]
}
con['02.06C - All Control Tabs Ready?'] = {
    'main': [
        [{'node': '02.07 - Prepare Control Header Batch', 'type': 'main', 'index': 0}],
        [{'node': '02.05B - Prepare Control Tab Create Attempt', 'type': 'main', 'index': 0}],
    ]
}

p.write_text(json.dumps(wf, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

# Documentation note
install = Path('docs/INSTALLATION.md')
text = install.read_text(encoding='utf-8')
marker = '## Google Sheets transient connection resets'
if marker not in text:
    text += '''\n\n## Google Sheets transient connection resets\n\nControl-tab creation is verification-driven. After a create attempt, n8n re-reads spreadsheet metadata and retries only tabs that are still missing, for at most three verified attempts. This safely recovers when Google closes a TLS socket and also avoids duplicate-sheet errors when a create request succeeded but its HTTP response was lost.\n'''
    install.write_text(text, encoding='utf-8')

# Validate
wf = json.loads(p.read_text(encoding='utf-8'))
n = {x['name']: x for x in wf['nodes']}
assert n['02.06 - Create Missing Control Tabs']['continueOnFail'] is True
assert n['02.06A - Verify Control Tabs After Create']['retryOnFail'] is True
assert wf['connections']['02.06C - All Control Tabs Ready?']['main'][1][0]['node'] == '02.05B - Prepare Control Tab Create Attempt'
print('workflow OK')
