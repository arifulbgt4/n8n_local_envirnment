import http from 'node:http';
import { Pool } from 'pg';

const PORT = Number(process.env.PORT || 3002);
const MAX_BODY_BYTES = Number(process.env.MAX_BODY_BYTES || 40 * 1024 * 1024);
const REQUEST_TIMEOUT_MS = Number(process.env.AI_REQUEST_TIMEOUT_MS || 120000);

const pool = new Pool({
  host: process.env.POSTGRES_HOST || 'postgres',
  port: Number(process.env.POSTGRES_PORT || 5432),
  database: process.env.POSTGRES_DB,
  user: process.env.POSTGRES_USER,
  password: process.env.POSTGRES_PASSWORD,
  max: Number(process.env.AI_GATEWAY_DB_POOL_MAX || 5),
});

function sendJson(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': Buffer.byteLength(payload),
  });
  res.end(payload);
}

async function readJson(req) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > MAX_BODY_BYTES) throw new Error(`Request body exceeds ${MAX_BODY_BYTES} bytes`);
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function text(value) {
  return String(value ?? '').trim();
}

function normalizeProvider(value) {
  const p = text(value).toLowerCase().replace(/\s+/g, '_');
  if (['openai', 'open_ai'].includes(p)) return 'openai';
  if (['anthropic', 'claude'].includes(p)) return 'anthropic';
  if (['gemini', 'google', 'google_gemini', 'google-gemini'].includes(p)) return 'gemini';
  if (['openai_compatible', 'openai-compatible', 'compatible', 'custom'].includes(p)) return 'openai_compatible';
  throw new Error(`Unsupported AI provider: ${value || '(blank)'}. Supported: openai, anthropic, gemini/google, openai_compatible.`);
}

function stripTrailingSlash(url) {
  return text(url).replace(/\/+$/, '');
}

function joinUrl(base, path) {
  return `${stripTrailingSlash(base)}/${String(path).replace(/^\/+/, '')}`;
}

function mimeForAnthropic(mime) {
  const m = text(mime).toLowerCase();
  if (m === 'image/jpg') return 'image/jpeg';
  if (['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(m)) return m;
  throw new Error(`Anthropic image input does not support MIME type ${mime || '(blank)'}`);
}

function extForMime(mime) {
  const m = text(mime).toLowerCase();
  if (m.includes('wav')) return 'wav';
  if (m.includes('webm')) return 'webm';
  if (m.includes('ogg')) return 'ogg';
  if (m.includes('mp4') || m.includes('m4a')) return 'm4a';
  if (m.includes('mpeg') || m.includes('mp3')) return 'mp3';
  if (m.includes('flac')) return 'flac';
  return 'bin';
}

async function fetchJson(url, options) {
  const response = await fetch(url, {
    ...options,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  const raw = await response.text();
  let data;
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = { raw };
  }
  if (!response.ok) {
    const providerMessage =
      data?.error?.message || data?.error?.status || data?.message || data?.raw || `HTTP ${response.status}`;
    throw new Error(`Provider request failed (${response.status}): ${String(providerMessage).slice(0, 1200)}`);
  }
  return data;
}

function extractOpenAIText(data) {
  if (typeof data?.output_text === 'string' && data.output_text.trim()) return data.output_text.trim();
  if (Array.isArray(data?.output)) {
    const out = [];
    for (const item of data.output) {
      for (const part of item?.content || []) {
        const t = part?.text || part?.output_text;
        if (typeof t === 'string' && t.trim()) out.push(t.trim());
      }
    }
    if (out.length) return out.join('\n');
  }
  if (Array.isArray(data?.choices)) {
    const t = data.choices[0]?.message?.content ?? data.choices[0]?.text;
    if (typeof t === 'string') return t.trim();
  }
  if (typeof data?.text === 'string') return data.text.trim();
  return '';
}

function extractAnthropicText(data) {
  return (data?.content || [])
    .filter((x) => x?.type === 'text' && typeof x?.text === 'string')
    .map((x) => x.text.trim())
    .filter(Boolean)
    .join('\n');
}

function extractGeminiText(data) {
  const parts = data?.candidates?.[0]?.content?.parts || [];
  return parts
    .map((x) => (typeof x?.text === 'string' ? x.text.trim() : ''))
    .filter(Boolean)
    .join('\n');
}

function normalizeUsage(provider, data) {
  if (provider === 'openai' || provider === 'openai_compatible') {
    const u = data?.usage || {};
    return {
      inputTokens: Number(u.input_tokens ?? u.prompt_tokens ?? 0) || 0,
      outputTokens: Number(u.output_tokens ?? u.completion_tokens ?? 0) || 0,
      totalTokens: Number(u.total_tokens ?? 0) || 0,
    };
  }
  if (provider === 'anthropic') {
    const u = data?.usage || {};
    const input = Number(u.input_tokens || 0) || 0;
    const output = Number(u.output_tokens || 0) || 0;
    return { inputTokens: input, outputTokens: output, totalTokens: input + output };
  }
  if (provider === 'gemini') {
    const u = data?.usageMetadata || {};
    return {
      inputTokens: Number(u.promptTokenCount || 0) || 0,
      outputTokens: Number(u.candidatesTokenCount || 0) || 0,
      totalTokens: Number(u.totalTokenCount || 0) || 0,
    };
  }
  return { inputTokens: 0, outputTokens: 0, totalTokens: 0 };
}

async function loadAccountConfig(accountId, purpose) {
  if (!/^\d+$/.test(String(accountId || ''))) throw new Error('A numeric accountId is required');
  const { rows } = await pool.query(
    `SELECT id::text AS account_id, account_key, ai_provider, ai_model, ai_api_key, ai_base_url,
            ai_audio_provider, ai_audio_model, ai_audio_api_key, ai_audio_base_url
       FROM business_accounts
      WHERE id=$1 AND active=TRUE
      LIMIT 1`,
    [String(accountId)],
  );
  if (!rows.length) throw new Error(`Active AI account ${accountId} was not found`);
  const row = rows[0];
  const isAudio = purpose === 'VOICE_TRANSCRIPTION';
  const providerRaw = isAudio ? text(row.ai_audio_provider) || text(row.ai_provider) : text(row.ai_provider);
  const model = isAudio ? text(row.ai_audio_model) || text(row.ai_model) : text(row.ai_model);
  const apiKey = isAudio ? text(row.ai_audio_api_key) || text(row.ai_api_key) : text(row.ai_api_key);
  const baseUrl = isAudio ? text(row.ai_audio_base_url) || text(row.ai_base_url) : text(row.ai_base_url);
  const provider = normalizeProvider(providerRaw);

  if (!model) throw new Error(`AI model is blank for account ${row.account_key || accountId}`);
  if (!apiKey) throw new Error(`AI API key is blank for account ${row.account_key || accountId}`);
  if (provider === 'openai_compatible' && !baseUrl) {
    throw new Error(`AI Base URL is required for openai_compatible account ${row.account_key || accountId}`);
  }

  return { provider, model, apiKey, baseUrl, accountKey: row.account_key };
}

async function callOpenAI({ model, apiKey, baseUrl, prompt, inputType, mediaBase64, mediaMimeType }) {
  const root = baseUrl || 'https://api.openai.com/v1';
  if (inputType === 'audio') {
    if (!/(transcrib|whisper)/i.test(model)) {
      throw new Error(`OpenAI audio requires a transcription-capable model in AI Audio Model (for example a transcription model), not ${model}`);
    }
    const bytes = Buffer.from(mediaBase64, 'base64');
    const form = new FormData();
    form.append('file', new Blob([bytes], { type: mediaMimeType || 'application/octet-stream' }), `audio.${extForMime(mediaMimeType)}`);
    form.append('model', model);
    if (prompt) form.append('prompt', prompt.slice(0, 4000));
    const response = await fetch(joinUrl(root, 'audio/transcriptions'), {
      method: 'POST',
      headers: { Authorization: `Bearer ${apiKey}` },
      body: form,
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    const raw = await response.text();
    let data;
    try { data = raw ? JSON.parse(raw) : {}; } catch { data = { raw }; }
    if (!response.ok) {
      const msg = data?.error?.message || data?.message || data?.raw || `HTTP ${response.status}`;
      throw new Error(`Provider request failed (${response.status}): ${String(msg).slice(0, 1200)}`);
    }
    return { data, text: text(data?.text) };
  }

  const content = [{ type: 'input_text', text: prompt }];
  if (inputType === 'image') {
    content.push({
      type: 'input_image',
      image_url: `data:${mediaMimeType || 'image/jpeg'};base64,${mediaBase64}`,
    });
  }
  const body = {
    model,
    input: [{ role: 'user', content }],
  };
  const data = await fetchJson(joinUrl(root, 'responses'), {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  return { data, text: extractOpenAIText(data) };
}

async function callAnthropic({ model, apiKey, baseUrl, prompt, inputType, mediaBase64, mediaMimeType }) {
  if (inputType === 'audio') {
    throw new Error('Anthropic audio input is not supported by this adapter. Set AI Audio Provider/Model/API Key for this account to a provider that supports audio, such as Gemini or an OpenAI transcription model.');
  }
  const root = baseUrl || 'https://api.anthropic.com';
  const content = [];
  if (inputType === 'image') {
    content.push({
      type: 'image',
      source: {
        type: 'base64',
        media_type: mimeForAnthropic(mediaMimeType),
        data: mediaBase64,
      },
    });
  }
  content.push({ type: 'text', text: prompt });
  const data = await fetchJson(joinUrl(root, 'v1/messages'), {
    method: 'POST',
    headers: {
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      model,
      max_tokens: 2048,
      messages: [{ role: 'user', content }],
    }),
  });
  return { data, text: extractAnthropicText(data) };
}

async function callGemini({ model, apiKey, baseUrl, prompt, inputType, mediaBase64, mediaMimeType }) {
  const root = baseUrl || 'https://generativelanguage.googleapis.com/v1beta';
  const cleanModel = model.replace(/^models\//, '');
  const parts = [{ text: prompt }];
  if (inputType === 'image' || inputType === 'audio') {
    parts.push({
      inlineData: {
        mimeType: mediaMimeType || (inputType === 'image' ? 'image/jpeg' : 'audio/mpeg'),
        data: mediaBase64,
      },
    });
  }
  const url = `${joinUrl(root, `models/${encodeURIComponent(cleanModel)}:generateContent`)}?key=${encodeURIComponent(apiKey)}`;
  const data = await fetchJson(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ contents: [{ role: 'user', parts }] }),
  });
  return { data, text: extractGeminiText(data) };
}

async function callOpenAICompatible({ model, apiKey, baseUrl, prompt, inputType, mediaBase64, mediaMimeType }) {
  if (inputType === 'audio') {
    throw new Error('Generic openai_compatible audio is not standardized. Configure AI Audio Provider as Gemini or OpenAI transcription, or use a provider-specific gateway adapter.');
  }
  const content = inputType === 'image'
    ? [
        { type: 'text', text: prompt },
        { type: 'image_url', image_url: { url: `data:${mediaMimeType || 'image/jpeg'};base64,${mediaBase64}` } },
      ]
    : prompt;
  const data = await fetchJson(joinUrl(baseUrl, 'chat/completions'), {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify({ model, messages: [{ role: 'user', content }] }),
  });
  return { data, text: extractOpenAIText(data) };
}

async function generate(body) {
  const accountId = body?.accountId;
  const purpose = text(body?.purpose).toUpperCase();
  const prompt = text(body?.prompt);
  const inputType = text(body?.inputType || 'text').toLowerCase();
  const mediaBase64 = text(body?.mediaBase64);
  const mediaMimeType = text(body?.mediaMimeType);

  if (!purpose) throw new Error('purpose is required');
  if (!prompt) throw new Error(`Prompt is blank for purpose ${purpose}`);
  if (!['text', 'image', 'audio'].includes(inputType)) throw new Error(`Unsupported inputType: ${inputType}`);
  if (inputType !== 'text' && !mediaBase64) throw new Error(`${inputType} input requires mediaBase64`);

  const config = await loadAccountConfig(accountId, purpose);
  const request = {
    model: config.model,
    apiKey: config.apiKey,
    baseUrl: config.baseUrl,
    prompt,
    inputType,
    mediaBase64,
    mediaMimeType,
  };

  let result;
  if (config.provider === 'openai') result = await callOpenAI(request);
  else if (config.provider === 'anthropic') result = await callAnthropic(request);
  else if (config.provider === 'gemini') result = await callGemini(request);
  else if (config.provider === 'openai_compatible') result = await callOpenAICompatible(request);
  else throw new Error(`Unsupported provider ${config.provider}`);

  const outputText = text(result.text);
  if (!outputText) throw new Error(`Provider ${config.provider} returned no text for ${purpose}`);

  return {
    ok: true,
    accountId: String(accountId),
    purpose,
    provider: config.provider,
    model: config.model,
    text: outputText,
    usage: normalizeUsage(config.provider, result.data),
  };
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/health') {
      await pool.query('SELECT 1');
      return sendJson(res, 200, { ok: true });
    }
    if (req.method === 'POST' && req.url === '/v1/generate') {
      const body = await readJson(req);
      const result = await generate(body);
      return sendJson(res, 200, result);
    }
    return sendJson(res, 404, { ok: false, error: 'Not found' });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`[ai-gateway] ${message}`);
    return sendJson(res, 400, { ok: false, error: message });
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[ai-gateway] listening on ${PORT}`);
});

async function shutdown() {
  server.close(async () => {
    await pool.end().catch(() => {});
    process.exit(0);
  });
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
