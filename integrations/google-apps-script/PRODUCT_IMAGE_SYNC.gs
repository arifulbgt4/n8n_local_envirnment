/**
 * AI Commerce V4.2 - Google Sheets direct-image synchronizer.
 *
 * The visible Products sheet stays human-friendly. Technical resolved-image,
 * Drive file-id and hash columns are created only for internal use and hidden.
 * Existing Image 2..5 columns are supported, but this script does NOT add them.
 *
 * Bind this script to each Operations Spreadsheet and run
 * installProductImageSyncTriggers() once.
 */
const PRODUCT_SHEET = 'Products';
const SOURCE_IMAGE_HEADERS = ['Product Image', 'Image 2', 'Image 3', 'Image 4', 'Image 5'];
const RESOLVED_HEADERS = ['Resolved Image 1', 'Resolved Image 2', 'Resolved Image 3', 'Resolved Image 4', 'Resolved Image 5'];
const FILE_ID_HEADERS = ['_Image File ID 1', '_Image File ID 2', '_Image File ID 3', '_Image File ID 4', '_Image File ID 5'];
const HASH_HEADERS = ['_Image Hash 1', '_Image Hash 2', '_Image Hash 3', '_Image Hash 4', '_Image Hash 5'];

function installProductImageSyncTriggers() {
  const ss = SpreadsheetApp.getActive();
  ScriptApp.getProjectTriggers().forEach(t => {
    if (['onProductSheetEdit', 'syncProductSheetImages'].includes(t.getHandlerFunction())) {
      ScriptApp.deleteTrigger(t);
    }
  });
  ScriptApp.newTrigger('onProductSheetEdit').forSpreadsheet(ss).onEdit().create();
  ScriptApp.newTrigger('syncProductSheetImages').timeBased().everyMinutes(5).create();
  syncProductSheetImages();
}

function onProductSheetEdit(e) {
  if (!e || !e.range || e.range.getSheet().getName() !== PRODUCT_SHEET) return;
  syncProductSheetImages();
}

function syncProductSheetImages() {
  const sh = SpreadsheetApp.getActive().getSheetByName(PRODUCT_SHEET);
  if (!sh) return;

  const map = ensureHeaders_(sh);
  formatProductSheet_(sh, map);
  if (sh.getLastRow() < 2) return;

  const over = new Map();
  sh.getImages().forEach(img => {
    try {
      const a = img.getAnchorCell();
      over.set(`${a.getRow()}:${a.getColumn()}`, img);
    } catch (_) {}
  });

  for (let row = 2; row <= sh.getLastRow(); row++) {
    for (let i = 0; i < SOURCE_IMAGE_HEADERS.length; i++) {
      const srcCol = map[SOURCE_IMAGE_HEADERS[i]];
      // Only Product Image is required. Image 2..5 are optional and are never
      // appended by this script, so old/simple product sheets stay clean.
      if (!srcCol) continue;
      syncImageSlot_(
        sh,
        row,
        srcCol,
        map[RESOLVED_HEADERS[i]],
        map[FILE_ID_HEADERS[i]],
        map[HASH_HEADERS[i]],
        over,
        i + 1
      );
    }
  }
}

function ensureHeaders_(sh) {
  let last = Math.max(1, sh.getLastColumn());
  let headers = sh.getRange(1, 1, 1, last).getDisplayValues()[0].map(v => String(v).trim());

  // Product Image is the only user-facing image column we require.
  if (!headers.includes('Product Image')) {
    headers.push('Product Image');
    sh.getRange(1, headers.length).setValue('Product Image');
  }

  // Internal helper columns are kept for n8n compatibility but hidden.
  const technical = [...RESOLVED_HEADERS, ...FILE_ID_HEADERS, ...HASH_HEADERS];
  technical.forEach(h => {
    if (!headers.includes(h)) {
      headers.push(h);
      sh.getRange(1, headers.length).setValue(h);
    }
  });

  const map = {};
  headers.forEach((h, i) => { if (h) map[h] = i + 1; });
  return map;
}

function formatProductSheet_(sh, map) {
  try { sh.setFrozenRows(1); } catch (_) {}

  // Hide all internal implementation details from the merchant-facing sheet.
  [...RESOLVED_HEADERS, ...FILE_ID_HEADERS, ...HASH_HEADERS].forEach(h => {
    const c = map[h];
    if (!c) return;
    try { sh.hideColumns(c); } catch (_) {}
  });

  // Old versions appended Image 2..5 automatically. If those columns are
  // completely empty, hide them so an existing simple sheet returns to a
  // clean layout. If the merchant actually uses one, it remains visible.
  ['Image 2', 'Image 3', 'Image 4', 'Image 5'].forEach(h => {
    const c = map[h];
    if (!c) return;
    let hasData = false;
    if (sh.getLastRow() > 1) {
      const vals = sh.getRange(2, c, sh.getLastRow() - 1, 1).getDisplayValues();
      hasData = vals.some(r => String(r[0] || '').trim() !== '');
    }
    if (!hasData) {
      try { sh.hideColumns(c); } catch (_) {}
    }
  });
}

function syncImageSlot_(sh, row, srcCol, resCol, idCol, hashCol, over, slot) {
  if (!srcCol || !resCol || !idCol || !hashCol) return;

  const src = sh.getRange(row, srcCol);
  const resolved = sh.getRange(row, resCol);
  const idCell = sh.getRange(row, idCol);
  const hashCell = sh.getRange(row, hashCol);
  const oldId = String(idCell.getDisplayValue() || '').trim();

  let url = extractUrl_(src);
  let blob = null;

  const grid = over.get(`${row}:${srcCol}`);
  if (grid) {
    try { blob = grid.getBlob(); } catch (_) {}
  }

  if (!blob && !url) {
    const v = src.getValue();
    if (v && typeof v === 'object' && typeof v.getContentUrl === 'function') {
      try { blob = UrlFetchApp.fetch(v.getContentUrl()).getBlob(); } catch (_) {}
    }
  }

  if (url) {
    trashFile_(oldId);
    resolved.setValue(url);
    idCell.clearContent();
    hashCell.clearContent();
    return;
  }

  if (blob) {
    const hash = blobHash_(blob);
    const oldHash = String(hashCell.getDisplayValue() || '').trim();
    if (oldId && oldHash === hash) {
      resolved.setValue(driveViewUrl_(oldId));
      return;
    }

    trashFile_(oldId);
    const ext = (blob.getContentType() || 'image/jpeg').split('/')[1] || 'jpg';
    const product = productFileKey_(sh, row);
    blob.setName(`${product}-image-${slot}.${ext}`);

    const file = DriveApp.createFile(blob);
    try { file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW); } catch (_) {}

    idCell.setValue(file.getId());
    hashCell.setValue(hash);
    resolved.setValue(driveViewUrl_(file.getId()));
    return;
  }

  // Source image was removed: remove the durable copy and technical refs too.
  trashFile_(oldId);
  resolved.clearContent();
  idCell.clearContent();
  hashCell.clearContent();
}

function productFileKey_(sh, row) {
  const headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getDisplayValues()[0].map(v => String(v).trim());
  const preferred = ['Product ID', 'SKU', 'Product Name', 'Name', 'Product'];
  for (const h of preferred) {
    const c = headers.indexOf(h);
    if (c >= 0) {
      const v = String(sh.getRange(row, c + 1).getDisplayValue() || '').trim();
      if (v) return v.replace(/[^\p{L}\p{N}\w\-.]+/gu, '_').slice(0, 80);
    }
  }
  return `row-${row}`;
}

function extractUrl_(cell) {
  const f = String(cell.getFormula() || '').trim();
  const m = f.match(/^=IMAGE\(\s*["']([^"']+)["']/i);
  if (m) return m[1];
  const v = cell.getDisplayValue();
  return /^https?:\/\//i.test(String(v || '').trim()) ? String(v).trim() : '';
}

function blobHash_(blob) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, blob.getBytes())
    .map(b => (b + 256) % 256)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

function driveViewUrl_(id) {
  return `https://drive.google.com/uc?export=view&id=${encodeURIComponent(id)}`;
}

function trashFile_(id) {
  if (!id) return;
  try { DriveApp.getFileById(id).setTrashed(true); } catch (_) {}
}
