from pathlib import Path

p = Path('scripts/externalize_ai_prompts.py')
s = p.read_text(encoding='utf-8')

if 'import re\n' not in s:
    s = s.replace('import json\n', 'import json\nimport re\n', 1)

old = '''def prompt_key_for(text: str) -> str:\n    if "Classify the customer message into exactly one label" in text:\n        return "INTENT_CLASSIFIER"\n    if "concise e-commerce sales assistant" in text:\n        return "PRODUCT_SEARCH_RESPONSE"\n    if text == "={{ $json._renderedAiPrompt }}":\n        # Already migrated; key is encoded in renderer node and no action is needed.\n        return ""\n    raise RuntimeError("Found an unrecognized hard-coded AI prompt")\n'''
new = '''def prompt_key_for(text: str, node_name: str) -> str:\n    if "Classify the customer message into exactly one label" in text:\n        return "INTENT_CLASSIFIER"\n    if "concise e-commerce sales assistant" in text:\n        return "PRODUCT_SEARCH_RESPONSE"\n    if text == "={{ $json._renderedAiPrompt }}":\n        return ""\n    key = re.sub(r"[^A-Z0-9]+", "_", str(node_name or "AI_PROMPT").upper()).strip("_")\n    return key or "AI_PROMPT"\n'''
if old not in s:
    raise SystemExit('prompt_key_for block not found')
s = s.replace(old, new, 1)
s = s.replace('key = prompt_key_for(old_text)', 'key = prompt_key_for(old_text, pnode["name"])', 1)

p.write_text(s, encoding='utf-8')
print('Patched migration to externalize every promptType=define node')
