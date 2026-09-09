/**
 * AI Commerce V4.2 - Products sheet normalizer + direct-image synchronizer.
 *
 * Goals:
 * - Existing product sheets are normalized in-place without deleting product data.
 * - Known/legacy/Bangla headers are renamed to canonical English headers.
 * - Missing canonical product columns are added automatically.
 * - Canonical columns are reordered into a consistent merchant-friendly layout.
 * - Legacy/custom columns are preserved but renamed to English Custom Field N and hidden.
 * - The full visible Products sheet is redesigned consistently (header, widths, rows,
 *   wrapping, filters, validation, alignment and number formatting).
 * - Direct Google Sheets images are copied to durable Drive URLs for n8n.
 * - Internal resolved-image/file-id/hash columns remain hidden.
 *
 * Bind this script to each Operations Spreadsheet and run
 * installProductImageSyncTriggers() once. No deployment is required.
 */
const PRODUCT_SHEET = 'Products';

const PRODUCT_COLUMNS = [
  'Product Name',
  'Category',
  'Subcategory',
  'Price',
  'Currency',
  'Product Description',
  'Product Image',
  'Image 2',
  'Image 3',
  'Image 4',
  'Image 5',
  'Product URL',
  'Color',
  'Size',
  'SKU',
  'Stock Status',
  'Stock Qty',
  'Offer',
  'Discount',
  'Aliases',
  'Active',
  'Product ID',
  'Product Group ID',
  'Variant ID',
  'Variant Name',
  'Updated At'
];

const SOURCE_IMAGE_HEADERS = ['Product Image', 'Image 2', 'Image 3', 'Image 4', 'Image 5'];
const RESOLVED_HEADERS = ['Resolved Image 1', 'Resolved Image 2', 'Resolved Image 3', 'Resolved Image 4', 'Resolved Image 5'];
const FILE_ID_HEADERS = ['_Image File ID 1', '_Image File ID 2', '_Image File ID 3', '_Image File ID 4', '_Image File ID 5'];
const HASH_HEADERS = ['_Image Hash 1', '_Image Hash 2', '_Image Hash 3', '_Image Hash 4', '_Image Hash 5'];
const TECHNICAL_HEADERS = [...RESOLVED_HEADERS, ...FILE_ID_HEADERS, ...HASH_HEADERS];

const HEADER_ALIASES = {
  'Product Name': ['Product Name', 'Name', 'Product', 'Item', 'Item Name', 'Title', 'Product Title', 'পণ্যের নাম', 'প্রোডাক্ট নাম', 'নাম'],
  'Category': ['Category', 'Product Category', 'Type', 'Product Type', 'ক্যাটাগরি', 'শ্রেণি', 'ধরন'],
  'Subcategory': ['Subcategory', 'Sub Category', 'Sub-Category', 'Collection', 'সাব ক্যাটাগরি', 'সাবক্যাটাগরি'],
  'Price': ['Price', 'Price (৳)', 'Price(৳)', 'Price Tk', 'Price BDT', 'Selling Price', 'Sale Price', 'Rate', 'Amount', 'মূল্য', 'দাম'],
  'Currency': ['Currency', 'Currency Code', 'মুদ্রা'],
  'Product Description': ['Product Description', 'Description', 'Details', 'Product Details', 'Description / Details', 'বিবরণ', 'ডিটেইলস', 'বিস্তারিত'],
  'Product Image': ['Product Image', 'Image', 'Photo', 'Picture', 'Product Photo', 'Image URL', 'Photo URL', 'ছবি', 'পণ্যের ছবি'],
  'Image 2': ['Image 2', 'Product Image 2', 'Photo 2', 'Picture 2'],
  'Image 3': ['Image 3', 'Product Image 3', 'Photo 3', 'Picture 3'],
  'Image 4': ['Image 4', 'Product Image 4', 'Photo 4', 'Picture 4'],
  'Image 5': ['Image 5', 'Product Image 5', 'Photo 5', 'Picture 5'],
  'Product URL': ['Product URL', 'Product Link', 'URL', 'Link', 'Page URL', 'Product Page URL', 'Website URL', 'Facebook URL', 'Post URL', 'পণ্যের লিংক', 'প্রোডাক্ট লিংক', 'লিংক'],
  'Color': ['Color', 'Colour', 'Product Color', 'রং', 'কালার'],
  'Size': ['Size', 'Sizes', 'Product Size', 'সাইজ'],
  'SKU': ['SKU', 'Sku', 'Product Code', 'Code', 'Item Code', 'কোড'],
  'Stock Status': ['Stock Status', 'Stock', 'Availability', 'Available', 'Inventory Status', 'স্টক', 'স্ট্যাটাস'],
  'Stock Qty': ['Stock Qty', 'Stock Quantity', 'Quantity', 'Qty', 'Inventory', 'Available Qty', 'পরিমাণ', 'স্টক পরিমাণ'],
  'Offer': ['Offer', 'Offer Text', 'Promotion', 'Promo', 'অফার'],
  'Discount': ['Discount', 'Discount %', 'Discount Percent', 'ছাড়', 'ডিসকাউন্ট'],
  'Aliases': ['Aliases', 'Alias', 'Keywords', 'Search Keywords', 'Tags', 'কিওয়ার্ড'],
  'Active': ['Active', 'Enabled', 'Is Active', 'Status Active', 'সক্রিয়'],
  'Product ID': ['Product ID', 'ProductID', 'ID', 'Item ID'],
  'Product Group ID': ['Product Group ID', 'Group ID', 'Parent Product ID', 'Parent ID'],
  'Variant ID': ['Variant ID', 'Variation ID', 'VariantID'],
  'Variant Name': ['Variant Name', 'Variation Name', 'Variant'],
  'Updated At': ['Updated At', 'Updated', 'Last Updated', 'Modified At', 'আপডেটেড']
};

function installProductImageSyncTriggers() {
  const ss = SpreadsheetApp.getActive();
  ScriptApp.getProjectTriggers().forEach(t => {
    if (['onProductSheetEdit', 'syncProductSheetImages'].includes(t.getHandlerFunction())) {
      ScriptApp.deleteTrigger(t);
    }
  });
  ScriptApp.newTrigger('onProductSheetEdit').forSpreadsheet(ss).onEdit().create();
  ScriptApp.newTrigger('syncProductSheetImages').timeBased().everyMinutes(5).create();
  normalizeProductSheetLayout();
  syncProductSheetImages();
}

function onProductSheetEdit(e) {
  if (!e || !e.range || e.range.getSheet().getName() !== PRODUCT_SHEET) return;
  syncProductSheetImages();
}

/** Public manual utility: safely normalize/reformat the whole Products sheet. */
function normalizeProductSheetLayout() {
  const sh = SpreadsheetApp.getActive().getSheetByName(PRODUCT_SHEET);
  if (!sh) return;
  normalizeProductSheetLayout_(sh);
}

function syncProductSheetImages() {
  const sh = SpreadsheetApp.getActive().getSheetByName(PRODUCT_SHEET);
  if (!sh) return;

  const map = normalizeProductSheetLayout_(sh);
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

function normalizeProductSheetLayout_(sh) {
  const lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) return headerMap_(sh);

  try {
    renameKnownAndLegacyHeaders_(sh);
    ensureCanonicalColumns_(sh);
    reorderCanonicalColumns_(sh);
    renameUnknownColumns_(sh);
    ensureTechnicalHeaders_(sh);

    const map = headerMap_(sh);
    formatProductSheet_(sh, map);
    return map;
  } finally {
    lock.releaseLock();
  }
}

function renameKnownAndLegacyHeaders_(sh) {
  const headers = readHeaders_(sh);
  const claimed = new Set();

  headers.forEach((raw, i) => {
    const h = String(raw || '').trim();
    if (!h || TECHNICAL_HEADERS.includes(h)) return;

    const canonical = canonicalHeader_(h);
    if (!canonical) return;

    // First matching legacy column becomes the canonical column. Duplicate
    // semantic columns are preserved and handled later as Custom Field N.
    if (!claimed.has(canonical)) {
      if (h !== canonical) sh.getRange(1, i + 1).setValue(canonical);
      claimed.add(canonical);
    }
  });
}

function ensureCanonicalColumns_(sh) {
  let headers = readHeaders_(sh);
  PRODUCT_COLUMNS.forEach(h => {
    if (headers.includes(h)) return;
    sh.insertColumnAfter(Math.max(1, sh.getLastColumn()));
    sh.getRange(1, sh.getLastColumn()).setValue(h);
    headers = readHeaders_(sh);
  });
}

function reorderCanonicalColumns_(sh) {
  PRODUCT_COLUMNS.forEach((h, targetZero) => {
    const target = targetZero + 1;
    const headers = readHeaders_(sh);
    const current = headers.indexOf(h) + 1;
    if (!current || current === target) return;
    const spec = sh.getRange(1, current, sh.getMaxRows(), 1);
    sh.moveColumns(spec, target);
  });
}

function renameUnknownColumns_(sh) {
  let headers = readHeaders_(sh);
  const canonicalSet = new Set(PRODUCT_COLUMNS);
  const technicalSet = new Set(TECHNICAL_HEADERS);
  let customNo = 1;

  // Canonical fields are already the first block. Everything else is legacy,
  // blank spacing, optional implementation metadata, or a custom merchant field.
  for (let c = PRODUCT_COLUMNS.length + 1; c <= headers.length; c++) {
    const raw = String(headers[c - 1] || '').trim();
    if (technicalSet.has(raw)) continue;

    if (!raw && !columnHasUserData_(sh, c)) {
      try { sh.hideColumns(c); } catch (_) {}
      continue;
    }

    if (canonicalSet.has(raw)) continue;
    if (/^Custom Field \d+$/i.test(raw)) {
      customNo++;
      continue;
    }

    const newName = `Custom Field ${customNo++}`;
    const cell = sh.getRange(1, c);
    if (raw) cell.setNote(`Original header: ${raw}`);
    cell.setValue(newName);
    try { sh.hideColumns(c); } catch (_) {}
  }
}

function ensureTechnicalHeaders_(sh) {
  let headers = readHeaders_(sh);
  TECHNICAL_HEADERS.forEach(h => {
    if (headers.includes(h)) return;
    sh.insertColumnAfter(Math.max(1, sh.getLastColumn()));
    sh.getRange(1, sh.getLastColumn()).setValue(h);
    headers = readHeaders_(sh);
  });
}

function formatProductSheet_(sh, map) {
  const lastRow = Math.max(1, sh.getLastRow());
  const visibleCount = PRODUCT_COLUMNS.length;

  try { sh.setFrozenRows(1); } catch (_) {}
  try { sh.setFrozenColumns(1); } catch (_) {}
  try {
    const f = sh.getFilter();
    if (f) f.remove();
  } catch (_) {}
  try {
    if (lastRow >= 1) sh.getRange(1, 1, lastRow, visibleCount).createFilter();
  } catch (_) {}

  try { sh.getBandings().forEach(b => b.remove()); } catch (_) {}

  const body = sh.getRange(1, 1, lastRow, visibleCount);
  body
    .setFontFamily('Arial')
    .setFontSize(10)
    .setFontColor('#202124')
    .setBackground('#FFFFFF')
    .setVerticalAlignment('middle')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);

  const header = sh.getRange(1, 1, 1, visibleCount);
  header
    .setBackground('#1F4E78')
    .setFontColor('#FFFFFF')
    .setFontWeight('bold')
    .setFontSize(11)
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');
  sh.setRowHeight(1, 36);

  if (lastRow > 1) {
    sh.setRowHeights(2, lastRow - 1, 96);
    // Light zebra striping without carrying over old random fills.
    for (let r = 2; r <= lastRow; r++) {
      if (r % 2 === 0) sh.getRange(r, 1, 1, visibleCount).setBackground('#F8FAFC');
    }
  }

  const widths = {
    'Product Name': 220, 'Category': 130, 'Subcategory': 140, 'Price': 100,
    'Currency': 85, 'Product Description': 380, 'Product Image': 150,
    'Image 2': 130, 'Image 3': 130, 'Image 4': 130, 'Image 5': 130,
    'Product URL': 240, 'Color': 100, 'Size': 100, 'SKU': 130,
    'Stock Status': 120, 'Stock Qty': 90, 'Offer': 160, 'Discount': 100,
    'Aliases': 180, 'Active': 80, 'Product ID': 150, 'Product Group ID': 160,
    'Variant ID': 160, 'Variant Name': 160, 'Updated At': 160
  };
  Object.entries(widths).forEach(([h, w]) => {
    const c = map[h];
    if (c) sh.setColumnWidth(c, w);
  });

  const left = ['Product Name', 'Category', 'Subcategory', 'Product Description', 'Product URL', 'Offer', 'Aliases', 'Variant Name'];
  const center = ['Currency', 'Product Image', 'Image 2', 'Image 3', 'Image 4', 'Image 5', 'Color', 'Size', 'SKU', 'Stock Status', 'Stock Qty', 'Discount', 'Active', 'Product ID', 'Product Group ID', 'Variant ID', 'Updated At'];
  if (lastRow > 1) {
    left.forEach(h => { const c = map[h]; if (c) sh.getRange(2, c, lastRow - 1, 1).setHorizontalAlignment('left'); });
    center.forEach(h => { const c = map[h]; if (c) sh.getRange(2, c, lastRow - 1, 1).setHorizontalAlignment('center'); });
    const priceCol = map['Price'];
    if (priceCol) sh.getRange(2, priceCol, lastRow - 1, 1).setHorizontalAlignment('right').setNumberFormat('#,##0.##');
    const qtyCol = map['Stock Qty'];
    if (qtyCol) sh.getRange(2, qtyCol, lastRow - 1, 1).setNumberFormat('0');

    const stockCol = map['Stock Status'];
    if (stockCol) {
      const rule = SpreadsheetApp.newDataValidation()
        .requireValueInList(['In Stock', 'Out of Stock', 'Preorder'], true)
        .setAllowInvalid(true)
        .build();
      sh.getRange(2, stockCol, lastRow - 1, 1).setDataValidation(rule);
    }

    const activeCol = map['Active'];
    if (activeCol) {
      const rule = SpreadsheetApp.newDataValidation().requireCheckbox().setAllowInvalid(true).build();
      sh.getRange(2, activeCol, lastRow - 1, 1).setDataValidation(rule);
    }
  }

  // Optional image columns remain available but are hidden while completely empty.
  ['Image 2', 'Image 3', 'Image 4', 'Image 5'].forEach(h => {
    const c = map[h];
    if (!c) return;
    const hasData = lastRow > 1 && columnHasUserData_(sh, c);
    try { if (hasData) sh.showColumns(c); else sh.hideColumns(c); } catch (_) {}
  });

  // Keep internal image implementation hidden from the merchant-facing sheet.
  TECHNICAL_HEADERS.forEach(h => {
    const c = map[h];
    if (c) try { sh.hideColumns(c); } catch (_) {}
  });

  // Hide preserved custom/legacy columns. Data is retained, and the original
  // header is kept in the header note.
  readHeaders_(sh).forEach((h, i) => {
    if (/^Custom Field \d+$/i.test(String(h || '').trim())) {
      try { sh.hideColumns(i + 1); } catch (_) {}
    }
  });
}

function canonicalHeader_(header) {
  const needle = normalizeHeader_(header);
  for (const canonical of PRODUCT_COLUMNS) {
    const aliases = HEADER_ALIASES[canonical] || [canonical];
    if (aliases.some(a => normalizeHeader_(a) === needle)) return canonical;
  }
  return '';
}

function normalizeHeader_(v) {
  return String(v || '')
    .trim()
    .toLowerCase()
    .replace(/[৳₹$€£]/g, '')
    .replace(/[()\[\]{}._\-/\\]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function readHeaders_(sh) {
  const last = Math.max(1, sh.getLastColumn());
  return sh.getRange(1, 1, 1, last).getDisplayValues()[0].map(v => String(v || '').trim());
}

function headerMap_(sh) {
  const map = {};
  readHeaders_(sh).forEach((h, i) => { if (h) map[h] = i + 1; });
  return map;
}

function columnHasUserData_(sh, col) {
  if (sh.getLastRow() < 2) return false;
  const values = sh.getRange(2, col, sh.getLastRow() - 1, 1).getDisplayValues();
  return values.some(r => String(r[0] || '').trim() !== '');
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
  const headers = readHeaders_(sh);
  const preferred = ['Product ID', 'SKU', 'Variant ID', 'Product Name'];
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
