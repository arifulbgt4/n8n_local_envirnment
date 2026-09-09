import http from 'node:http';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const PORT = Number(process.env.PORT || 3001);
const CACHE_DIR = process.env.CACHE_DIR || '/data/product-media';
const MAX_IMAGE_BYTES = Number(process.env.MAX_IMAGE_BYTES || 25 * 1024 * 1024);
const DEFAULT_GRAPH_VERSION = process.env.GRAPH_VERSION || 'v26.0';

await fs.mkdir(CACHE_DIR, { recursive: true });

function json(res, status, body) {
  const payload = Buffer.from(JSON.stringify(body));
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'content-length': payload.length,
    'cache-control': 'no-store',
  });
  res.end(payload);
}

async function readBody(req) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > 1024 * 1024) throw new Error('request body too large');
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function safeKey(value) {
  const raw = String(value || 'media').trim();
  return raw.replace(/[^a-zA-Z0-9._-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 140) || 'media';
}

function normalizeDriveUrl(input) {
  const source = String(input || '').trim();
  try {
    const u = new URL(source);
    if (u.hostname === 'drive.google.com') {
      let id = u.searchParams.get('id');
      if (!id) {
        const m = u.pathname.match(/\/file\/d\/([^/]+)/);
        if (m) id = m[1];
      }
      if (id) {
        return `https://drive.usercontent.google.com/download?id=${encodeURIComponent(id)}&export=download&confirm=t`;
      }
    }
  } catch {}
  return source;
}

async function exists(file) {
  try { await fs.access(file); return true; } catch { return false; }
}

async function readMeta(file) {
  try { return JSON.parse(await fs.readFile(file, 'utf8')); } catch { return null; }
}

async function cacheImage(sourceUrl, cacheKey) {
  if (!/^https?:\/\//i.test(String(sourceUrl || ''))) throw new Error('sourceUrl must be http/https');
  const key = safeKey(cacheKey || crypto.createHash('sha256').update(String(sourceUrl)).digest('hex').slice(0, 32));
  const localPath = path.join(CACHE_DIR, `${key}.bin`);
  const metaPath = path.join(CACHE_DIR, `${key}.json`);
  const old = await readMeta(metaPath);

  if (old && old.sourceUrl === sourceUrl && await exists(localPath)) {
    const stat = await fs.stat(localPath);
    return {
      cacheKey: key,
      localPath,
      mimeType: old.mimeType || 'application/octet-stream',
      fileSize: stat.size,
      reusedLocalFile: true,
    };
  }

  const fetchUrl = normalizeDriveUrl(sourceUrl);
  const response = await fetch(fetchUrl, { redirect: 'follow' });
  if (!response.ok) throw new Error(`source image download failed (${response.status})`);
  const mimeType = String(response.headers.get('content-type') || '').split(';')[0].trim().toLowerCase();
  if (!mimeType.startsWith('image/')) throw new Error(`source did not return an image (${mimeType || 'unknown content-type'})`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (!bytes.length) throw new Error('source image is empty');
  if (bytes.length > MAX_IMAGE_BYTES) throw new Error(`image exceeds ${MAX_IMAGE_BYTES} bytes`);

  const tmp = `${localPath}.tmp-${process.pid}-${Date.now()}`;
  await fs.writeFile(tmp, bytes);
  await fs.rename(tmp, localPath);
  await fs.writeFile(metaPath, JSON.stringify({
    sourceUrl,
    normalizedSourceUrl: fetchUrl,
    mimeType,
    fileSize: bytes.length,
    sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
    cachedAt: new Date().toISOString(),
  }, null, 2));

  return { cacheKey: key, localPath, mimeType, fileSize: bytes.length, reusedLocalFile: false };
}

async function graphJson(url, accessToken, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${accessToken}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!response.ok || data?.error) {
    throw new Error(data?.error?.message || `Meta request failed (${response.status})`);
  }
  return data;
}

async function sendAttachmentId({ accessToken, recipientId, attachmentId, graphVersion }) {
  return graphJson(`https://graph.facebook.com/${graphVersion}/me/messages`, accessToken, {
    recipient: { id: String(recipientId) },
    messaging_type: 'RESPONSE',
    message: { attachment: { type: 'image', payload: { attachment_id: String(attachmentId) } } },
  });
}

async function uploadReusableAttachment({ accessToken, localPath, mimeType, graphVersion }) {
  const bytes = await fs.readFile(localPath);
  const form = new FormData();
  form.append('message', JSON.stringify({ attachment: { type: 'image', payload: { is_reusable: true } } }));
  form.append('filedata', new Blob([bytes], { type: mimeType || 'image/jpeg' }), path.basename(localPath));
  const response = await fetch(`https://graph.facebook.com/${graphVersion}/me/message_attachments`, {
    method: 'POST',
    headers: { authorization: `Bearer ${accessToken}` },
    body: form,
  });
  const text = await response.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }
  if (!response.ok || data?.error || !data?.attachment_id) {
    throw new Error(data?.error?.message || `Meta attachment upload failed (${response.status})`);
  }
  return String(data.attachment_id);
}

async function handleFacebookSend(body) {
  const accessToken = String(body.accessToken || '');
  const recipientId = String(body.recipientId || '');
  const sourceUrl = String(body.sourceUrl || '');
  const graphVersion = String(body.graphVersion || DEFAULT_GRAPH_VERSION).replace(/^\/+/, '');
  let attachmentId = String(body.attachmentId || '');
  if (!accessToken || !recipientId) throw new Error('accessToken and recipientId are required');

  if (attachmentId) {
    try {
      const sent = await sendAttachmentId({ accessToken, recipientId, attachmentId, graphVersion });
      return {
        ok: true,
        messageId: String(sent.message_id || ''),
        attachmentId,
        reusedAttachment: true,
        reusedLocalFile: true,
        cacheKey: String(body.cacheKey || ''),
        localPath: String(body.localPath || ''),
        mimeType: String(body.mimeType || ''),
        fileSize: Number(body.fileSize || 0),
      };
    } catch {
      attachmentId = '';
    }
  }

  if (!sourceUrl) throw new Error('sourceUrl is required when no reusable attachmentId is available');
  const cached = await cacheImage(sourceUrl, body.cacheKey);
  attachmentId = await uploadReusableAttachment({
    accessToken,
    localPath: cached.localPath,
    mimeType: cached.mimeType,
    graphVersion,
  });
  const sent = await sendAttachmentId({ accessToken, recipientId, attachmentId, graphVersion });
  return {
    ok: true,
    messageId: String(sent.message_id || ''),
    attachmentId,
    reusedAttachment: false,
    ...cached,
  };
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    if (req.method === 'GET' && url.pathname === '/health') {
      return json(res, 200, { ok: true, service: 'product-media-cache' });
    }
    if (req.method === 'POST' && url.pathname === '/v1/cache') {
      const body = await readBody(req);
      const result = await cacheImage(String(body.sourceUrl || ''), String(body.cacheKey || ''));
      return json(res, 200, { ok: true, ...result });
    }
    if (req.method === 'POST' && url.pathname === '/v1/facebook/send-image') {
      const body = await readBody(req);
      const result = await handleFacebookSend(body);
      return json(res, 200, result);
    }
    return json(res, 404, { ok: false, error: 'not found' });
  } catch (error) {
    return json(res, 502, { ok: false, error: String(error?.message || error) });
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`product-media-cache listening on :${PORT}`);
});
