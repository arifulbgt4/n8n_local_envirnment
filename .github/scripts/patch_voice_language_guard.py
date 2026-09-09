import json
from pathlib import Path

TARGET = Path('workflows/modular/05_META_MESSAGING_V4_2.json')
WORKFLOW = Path('.github/workflows/patch-voice-language-guard.yml')
SCRIPT = Path('.github/scripts/patch_voice_language_guard.py')

data = json.loads(TARGET.read_text())
nodes = {n.get('name'): n for n in data.get('nodes', [])}

required = [
    'Transcribe Voice',
    'Attach Voice Transcript',
    'AI Intent Classifier',
    'Product Answer AI',
    'Order Details Extract AI',
    'General Answer AI',
]
missing = [name for name in required if name not in nodes]
if missing:
    raise SystemExit('Missing expected nodes: ' + ', '.join(missing))

# Bias speech-to-text toward Bengali for Bangla/Banglish customers.
transcribe = nodes['Transcribe Voice']['parameters']
options = transcribe.setdefault('options', {})
options['language'] = 'bn'

# Preserve voice context for downstream language handling.
nodes['Attach Voice Transcript']['parameters']['jsCode'] = """const base = $('Only Audio Binary').item.json;
const transcript = $json.text || $json.transcription || $json.content || '';
const text = String(transcript || '').trim();
const unclear = !text || text.length < 2;
return [{json:{
  ...base,
  message:text,
  normalizedQuestion:text.toLowerCase(),
  inputSource:'voice',
  preferredReplyLanguage:'bn',
  voiceTranscriptUnclear:unclear
}}];"""

classifier_guard = """

VOICE/LANGUAGE GUARD:
- If inputSource is `voice`, treat the customer as Bengali/Bangla by default. Bengali voice may contain English product names, brands, numbers, sizes, or Banglish words.
- Do not treat a suspicious foreign-language transcription as proof that the customer wants that language.
- If the voice transcript is empty or clearly nonsensical/unclear, classify it as GENERAL rather than guessing a product/order intent.
Input source: {{ $json.inputSource || 'text' }}
Preferred reply language: {{ $json.preferredReplyLanguage || '' }}
Voice transcript unclear: {{ $json.voiceTranscriptUnclear || false }}
"""

reply_guard = """

VOICE/LANGUAGE GUARD:
- If inputSource is `voice`, reply in Bengali (Bangla) by default, even if the transcript appears to be Polish or another unrelated language.
- Bengali voice may mix English product names, brands, numbers, sizes, and common Banglish words.
- Never switch to Polish or another unrelated language because of uncertain transcription.
- If the voice transcript is empty, nonsensical, or unclear, reply exactly in Bengali: \"আপনার ভয়েসটি পরিষ্কার বুঝতে পারিনি। আরেকবার বলবেন?\"
- For normal text input, continue replying in the customer's actual language/style.
Input source: {{ $json.inputSource || 'text' }}
Preferred reply language: {{ $json.preferredReplyLanguage || '' }}
Voice transcript unclear: {{ $json.voiceTranscriptUnclear || false }}
"""

p = nodes['AI Intent Classifier'].get('parameters', {})
if isinstance(p.get('text'), str) and 'VOICE/LANGUAGE GUARD:' not in p['text']:
    p['text'] += classifier_guard

for name in ['Product Answer AI', 'Order Details Extract AI', 'General Answer AI']:
    p = nodes[name].get('parameters', {})
    if isinstance(p.get('text'), str) and 'VOICE/LANGUAGE GUARD:' not in p['text']:
        p['text'] += reply_guard

TARGET.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
json.loads(TARGET.read_text())

# One-time patch cleanup.
if WORKFLOW.exists():
    WORKFLOW.unlink()
if SCRIPT.exists():
    SCRIPT.unlink()

print('Patched Bengali voice transcription and reply language guard.')
