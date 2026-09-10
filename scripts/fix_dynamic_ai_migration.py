from pathlib import Path

p = Path('scripts/migrate_dynamic_ai_provider.py')
s = p.read_text(encoding='utf-8')
old = """# Remove static OpenAI/LangChain execution nodes. Renderers and parsers remain.\nremove_names = {\n    'OpenAI Chat Model - Core',\n    'AI Intent Classifier',\n    'Product Answer AI',\n    'Order Details Extract AI',\n    'General Answer AI',\n    'Analyze Product Image',\n    'Transcribe Voice',\n}\nmissing = [n for n in remove_names if n not in by_name]\nif missing:\n    raise RuntimeError(f'Expected legacy AI nodes were not found: {missing}')\n\nnodes[:] = [n for n in nodes if n['name'] not in remove_names]\n"""
new = """# Remove every current static LangChain/provider AI execution node. Renderers and parsers remain.\nlegacy_named = {\n    'OpenAI Chat Model - Core',\n    'AI Intent Classifier',\n    'Product Answer AI',\n    'Order Details Extract AI',\n    'General Answer AI',\n    'Analyze Product Image',\n    'Transcribe Voice',\n}\nlangchain_names = {\n    n['name'] for n in nodes\n    if str(n.get('type', '')).startswith('@n8n/n8n-nodes-langchain.')\n}\nremove_names = langchain_names | {name for name in legacy_named if name in by_name}\n\nrequired_runtime_nodes = {\n    'Only Audio Binary', 'Attach Voice Transcript', 'Only Image Binary', 'Attach Image Analysis',\n    'Parse AI Intent', 'Parse Product Answer', 'Parse Order Details', 'Parse General Answer',\n    'Render AI Prompt - INTENT_CLASSIFIER', 'Render AI Prompt - PRODUCT_SEARCH_RESPONSE',\n    'Render AI Prompt - ORDER_DETAILS_EXTRACT_AI', 'Render AI Prompt - GENERAL_ANSWER_AI',\n    'Render AI Prompt - IMAGE_PRODUCT_ANALYSIS',\n}\nmissing_runtime = sorted(required_runtime_nodes - set(by_name))\nif missing_runtime:\n    raise RuntimeError(f'Required provider-neutral runtime nodes are missing: {missing_runtime}')\n\nnodes[:] = [n for n in nodes if n['name'] not in remove_names]\n"""
if old not in s:
    raise SystemExit('Target legacy-AI removal block not found; migration script changed unexpectedly')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('Dynamic AI migration compatibility patch applied')
