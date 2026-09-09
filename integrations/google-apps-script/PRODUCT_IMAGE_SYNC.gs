/**
 * AI Commerce V4.2 - Products sheet synchronizer.
 *
 * This script treats the Products sheet as a merchant-facing source of truth.
 * It normalizes legacy headers to canonical English names, adds missing columns,
 * removes layout noise, trims text, safely consolidates duplicate rows, preserves
 * real variants, resolves direct images to durable Drive URLs, and keeps internal
 * image metadata hidden for n8n.
 *
 * Bind this script to each Operations Spreadsheet and run
 * installProductImageSyncTriggers() once. No deployment is required.
 */

const PRODUCT_SHEET = 'Products';
const SCRIPT_VERSION = '4.2-products-v3';
const IMAGE_REGISTRY_KEY = 'PRODUCT_IMAGE_FILE_REGISTRY_V3';

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

const IMAGE_HEADERS = ['Product Image', 'Image 2', 'Image 3', 'Image 4', 'Image 5'];
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

const NORMALIZED_ALIAS_MAP = (() => {
  const out = {};
  Object.entries(HEADER_ALIASES).forEach(([canonical, aliases]) => {
    aliases.forEach(alias => { out[normalizeHeaderKey_(alias)] = canonical; });
    out[normalizeHeaderKey_(canonical)] = canonical;
  });
  return out;
})();

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

/** Manual utility. Runs the same full synchronization used by the triggers. */
function normalizeProductSheetLayout() {
  syncProductSheetImages();
}

function syncProductSheetImages() {
  const sh = SpreadsheetApp.getActive().getSheetByName(PRODUCT_SHEET);
  if (!sh) return;

  const lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) return;

  try {
    ensureOneTimeBackup_(sh);
    const snapshot = snapshotProducts_(sh);
    const normalizedRows = snapshot.rows.map(r => normalizeProductRow_(r, snapshot.customHeaders));
    const mergedRows = consolidateDuplicateRows_(normalizedRows, snapshot.customHeaders);
    finalizeIds_(mergedRows);
    rebuildProductsSheet_(sh, mergedRows, snapshot.customHeaders);
    cleanupManagedImageFiles_(mergedRows);
    PropertiesService.getScriptProperties().setProperty('PRODUCT_SHEET_SCHEMA_VERSION', SCRIPT_VERSION);
  } finally {
    lock.releaseLock();
  }
}

function ensureOneTimeBackup_(sh) {
  const ss = sh.getParent();
  const existing = ss.getSheets().some(s => /^_Products_Backup_/.test(s.getName()));
  if (existing) return;
  try {
    const stamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone() || 'Asia/Dhaka', 'yyyyMMdd_HHmmss');
    const backup = sh.copyTo(ss).setName(`_Products_Backup_${stamp}`);
    backup.hideSheet();
  } catch (_) {}
}

function snapshotProducts_(sh) {
  const lastRow = Math.max(1, sh.getLastRow());
  const lastCol = Math.max(1, sh.getLastColumn());
  const headersRaw = sh.getRange(1, 1, 1, lastCol).getDisplayValues()[0].map(v => cleanLine_(v));
  const values = lastRow > 1 ? sh.getRange(2, 1, lastRow - 1, lastCol).getValues() : [];
  const displays = lastRow > 1 ? sh.getRange(2, 1, lastRow - 1, lastCol).getDisplayValues() : [];
  const formulas = lastRow > 1 ? sh.getRange(2, 1, lastRow - 1, lastCol).getFormulas() : [];

  const canonicalCols = {};
  PRODUCT_COLUMNS.forEach(h => { canonicalCols[h] = []; });
  const techCols = {};
  TECHNICAL_HEADERS.forEach(h => { techCols[h] = -1; });
  const unknownCols = [];

  headersRaw.forEach((raw, i) => {
    if (TECHNICAL_HEADERS.includes(raw)) {
      techCols[raw] = i;
      return;
    }
    const canonical = canonicalHeader_(raw);
    if (canonical) {
      canonicalCols[canonical].push(i);
      return;
    }
    if (raw || columnHasDataInArrays_(values, displays, i)) unknownCols.push({ index: i, original: raw || `Column ${i + 1}` });
  });

  const customHeaders = unknownCols.map((c, i) => ({
    index: c.index,
    original: c.original,
    name: `Custom Field ${i + 1}`
  }));

  const overGrid = new Map();
  try {
    sh.getImages().forEach(img => {
      try {
        const a = img.getAnchorCell();
        overGrid.set(`${a.getRow()}:${a.getColumn()}`, img);
      } catch (_) {}
    });
  } catch (_) {}

  const rows = [];
  for (let r = 0; r < values.length; r++) {
    const sheetRow = r + 2;
    const hasAny = displays[r].some(v => cleanLine_(v) !== '') || IMAGE_HEADERS.some(h => {
      return canonicalCols[h].some(idx => overGrid.has(`${sheetRow}:${idx + 1}`));
    });
    if (!hasAny) continue;

    const row = { canonical: {}, custom: {}, images: [], imageMeta: [] };
    PRODUCT_COLUMNS.forEach(h => {
      if (IMAGE_HEADERS.includes(h)) return;
      row.canonical[h] = firstMeaningfulCell_(values[r], displays[r], formulas[r], canonicalCols[h]);
    });
    customHeaders.forEach(c => {
      row.custom[c.name] = cleanMultiline_(displays[r][c.index]);
    });

    IMAGE_HEADERS.forEach((h, slotIndex) => {
      const sourceIndices = canonicalCols[h];
      const image = resolveImageSlotFromSnapshot_(
        sh,
        sheetRow,
        sourceIndices,
        values[r],
        displays[r],
        formulas[r],
        overGrid,
        techCols[RESOLVED_HEADERS[slotIndex]],
        techCols[FILE_ID_HEADERS[slotIndex]],
        techCols[HASH_HEADERS[slotIndex]]
      );
      row.images.push(image.url || '');
      row.imageMeta.push(image);
    });
    rows.push(row);
  }

  return { rows, customHeaders };
}

function normalizeProductRow_(row, customHeaders) {
  const c = row.canonical;
  const out = {
    'Product Name': cleanLine_(c['Product Name']),
    'Category': cleanLine_(c['Category']),
    'Subcategory': cleanLine_(c['Subcategory']),
    'Price': parseNumber_(c['Price']),
    'Currency': (cleanLine_(c['Currency']) || 'BDT').toUpperCase(),
    'Product Description': cleanMultiline_(c['Product Description']),
    'Product URL': cleanUrl_(c['Product URL']),
    'Color': cleanLine_(c['Color']),
    'Size': cleanLine_(c['Size']),
    'SKU': cleanLine_(c['SKU']),
    'Stock Status': normalizeStockStatus_(c['Stock Status']),
    'Stock Qty': parseInteger_(c['Stock Qty']),
    'Offer': cleanMultiline_(c['Offer']),
    'Discount': cleanLine_(c['Discount']),
    'Aliases': cleanLine_(c['Aliases']),
    'Active': parseBoolean_(c['Active'], true),
    'Product ID': cleanLine_(c['Product ID']),
    'Product Group ID': cleanLine_(c['Product Group ID']),
    'Variant ID': cleanLine_(c['Variant ID']),
    'Variant Name': cleanLine_(c['Variant Name']),
    'Updated At': normalizeUpdatedAt_(c['Updated At'])
  };

  if (!out['Stock Status'] && out['Stock Qty'] !== null) {
    out['Stock Status'] = out['Stock Qty'] > 0 ? 'In Stock' : 'Out of Stock';
  }
  if (!out['Stock Status']) out['Stock Status'] = 'In Stock';

  const images = [];
  const meta = [];
  row.images.forEach((url, i) => {
    const clean = cleanUrl_(url);
    if (!clean || images.includes(clean) || images.length >= 5) return;
    images.push(clean);
    meta.push({ ...row.imageMeta[i], url: clean });
  });
  while (images.length < 5) images.push('');
  while (meta.length < 5) meta.push({ url: '', fileId: '', hash: '', managed: false });
  out._images = images;
  out._imageMeta = meta;
  out._custom = {};
  customHeaders.forEach(h => { out._custom[h.name] = cleanMultiline_(row.custom[h.name]); });
  return out;
}

function consolidateDuplicateRows_(rows, customHeaders) {
  const map = new Map();

  rows.forEach(row => {
    if (!row['Product Name']) return;
    const key = productIdentityKey_(row, customHeaders);
    if (!map.has(key)) {
      map.set(key, cloneProductRow_(row));
      return;
    }
    const base = map.get(key);
    mergeProductRows_(base, row, customHeaders);
  });

  return [...map.values()];
}

function productIdentityKey_(row, customHeaders) {
  // A real variant must remain separate. Same product repeated only because of
  // different images will have the same key and its images will be consolidated.
  const explicitVariant = cleanKey_(row['Variant ID'] || row['SKU']);
  if (explicitVariant) return `variant:${explicitVariant}`;

  const customKey = customHeaders.map(h => cleanKey_(row._custom[h.name])).filter(Boolean).join('|');
  return [
    cleanKey_(row['Product Name']),
    normalizeNumberKey_(row['Price']),
    cleanKey_(row['Category']),
    cleanKey_(row['Subcategory']),
    cleanKey_(row['Color']),
    cleanKey_(row['Size']),
    cleanKey_(row['Product ID']),
    cleanKey_(row['Product URL']),
    cleanKey_(row['Product Description']),
    customKey
  ].join('¦');
}

function cloneProductRow_(row) {
  return {
    ...row,
    _images: [...row._images],
    _imageMeta: row._imageMeta.map(x => ({ ...x })),
    _custom: { ...row._custom }
  };
}

function mergeProductRows_(base, incoming, customHeaders) {
  const mergedImages = [];
  const mergedMeta = [];
  [...base._images, ...incoming._images].forEach((url, idx) => {
    const clean = cleanUrl_(url);
    if (!clean || mergedImages.includes(clean) || mergedImages.length >= 5) return;
    mergedImages.push(clean);
    const sourceMeta = idx < base._images.length ? base._imageMeta[idx] : incoming._imageMeta[idx - base._images.length];
    mergedMeta.push({ ...(sourceMeta || {}), url: clean });
  });
  while (mergedImages.length < 5) mergedImages.push('');
  while (mergedMeta.length < 5) mergedMeta.push({ url: '', fileId: '', hash: '', managed: false });
  base._images = mergedImages;
  base._imageMeta = mergedMeta;

  const preferLonger = ['Product Description', 'Offer', 'Aliases'];
  preferLonger.forEach(k => {
    if (String(incoming[k] || '').length > String(base[k] || '').length) base[k] = incoming[k];
  });

  const fillIfBlank = ['Category', 'Subcategory', 'Currency', 'Product URL', 'Color', 'Size', 'SKU', 'Product ID', 'Product Group ID', 'Variant ID', 'Variant Name', 'Discount'];
  fillIfBlank.forEach(k => { if (!base[k] && incoming[k]) base[k] = incoming[k]; });

  if (base['Price'] === null && incoming['Price'] !== null) base['Price'] = incoming['Price'];
  if (base['Stock Qty'] === null) base['Stock Qty'] = incoming['Stock Qty'];
  else if (incoming['Stock Qty'] !== null) base['Stock Qty'] = Math.max(base['Stock Qty'], incoming['Stock Qty']);
  if (incoming['Stock Status'] === 'In Stock') base['Stock Status'] = 'In Stock';
  base['Active'] = base['Active'] || incoming['Active'];
  base['Updated At'] = latestDateText_(base['Updated At'], incoming['Updated At']);

  customHeaders.forEach(h => {
    const a = cleanMultiline_(base._custom[h.name]);
    const b = cleanMultiline_(incoming._custom[h.name]);
    if (!a) base._custom[h.name] = b;
    else if (b && a !== b) base._custom[h.name] = `${a} | ${b}`;
  });
}

function finalizeIds_(rows) {
  const seenProductIds = new Set();
  rows.forEach((row, i) => {
    const group = cleanLine_(row['Product Group ID']) || slugify_(row['Product Name']) || `product-${i + 1}`;
    row['Product Group ID'] = group;

    if (!row['Variant Name']) row['Variant Name'] = [row['Color'], row['Size']].filter(Boolean).join(' / ');
    if (!row['Variant ID']) {
      const suffix = [row['Color'], row['Size'], row['SKU']].filter(Boolean).join('-');
      row['Variant ID'] = slugify_(suffix ? `${group}-${suffix}` : group) || group;
    }

    let productId = cleanLine_(row['Product ID']) || row['Variant ID'];
    if (seenProductIds.has(productId)) {
      let n = 2;
      const base = productId;
      while (seenProductIds.has(`${base}-${n}`)) n++;
      productId = `${base}-${n}`;
    }
    row['Product ID'] = productId;
    seenProductIds.add(productId);
    if (!row['Updated At']) row['Updated At'] = new Date().toISOString();
  });
}

function rebuildProductsSheet_(sh, rows, customHeaders) {
  const visibleHeaders = [...PRODUCT_COLUMNS, ...customHeaders.map(h => h.name)];
  const allHeaders = [...visibleHeaders, ...TECHNICAL_HEADERS];
  const requiredCols = allHeaders.length;
  const requiredRows = Math.max(2, rows.length + 1);

  try { sh.getImages().forEach(img => { try { img.remove(); } catch (_) {} }); } catch (_) {}

  if (sh.getMaxColumns() < requiredCols) {
    sh.insertColumnsAfter(sh.getMaxColumns(), requiredCols - sh.getMaxColumns());
  } else if (sh.getMaxColumns() > requiredCols) {
    sh.deleteColumns(requiredCols + 1, sh.getMaxColumns() - requiredCols);
  }
  if (sh.getMaxRows() < requiredRows) {
    sh.insertRowsAfter(sh.getMaxRows(), requiredRows - sh.getMaxRows());
  }

  sh.clear();
  sh.getRange(1, 1, 1, requiredCols).setValues([allHeaders]);

  if (rows.length) {
    const data = rows.map(row => {
      const visible = PRODUCT_COLUMNS.map(h => {
        const imageIndex = IMAGE_HEADERS.indexOf(h);
        if (imageIndex >= 0) {
          const url = row._images[imageIndex] || '';
          return url ? imageFormula_(url) : '';
        }
        return row[h] === null || row[h] === undefined ? '' : row[h];
      });
      customHeaders.forEach(h => visible.push(row._custom[h.name] || ''));

      const resolved = row._images.map(x => x || '');
      const ids = row._imageMeta.map(x => x && x.managed ? (x.fileId || '') : '');
      const hashes = row._imageMeta.map(x => x && x.managed ? (x.hash || '') : '');
      return [...visible, ...resolved, ...ids, ...hashes];
    });
    sh.getRange(2, 1, data.length, requiredCols).setValues(data);
  }

  customHeaders.forEach((h, i) => {
    sh.getRange(1, PRODUCT_COLUMNS.length + i + 1).setNote(`Original header: ${h.original}`);
  });

  formatProductsSheet_(sh, visibleHeaders, rows.length);
  const technicalStart = visibleHeaders.length + 1;
  try { sh.hideColumns(technicalStart, TECHNICAL_HEADERS.length); } catch (_) {}
}

function formatProductsSheet_(sh, visibleHeaders, rowCount) {
  const visibleCount = visibleHeaders.length;
  const lastRow = Math.max(1, rowCount + 1);
  try { sh.setHiddenGridlines(true); } catch (_) {}
  try { sh.setFrozenRows(1); } catch (_) {}
  try { sh.setFrozenColumns(1); } catch (_) {}
  try { const f = sh.getFilter(); if (f) f.remove(); } catch (_) {}

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

  if (rowCount > 0) {
    for (let r = 2; r <= rowCount + 1; r++) {
      const desc = String(sh.getRange(r, PRODUCT_COLUMNS.indexOf('Product Description') + 1).getDisplayValue() || '');
      const lines = Math.max(1, desc.split(/\n/).length);
      const height = Math.min(112, Math.max(72, 52 + Math.min(lines, 4) * 12));
      sh.setRowHeight(r, height);
      if (r % 2 === 0) sh.getRange(r, 1, 1, visibleCount).setBackground('#F8FAFC');
    }
  }

  const widths = {
    'Product Name': 220, 'Category': 130, 'Subcategory': 140, 'Price': 100,
    'Currency': 80, 'Product Description': 360, 'Product Image': 120,
    'Image 2': 110, 'Image 3': 110, 'Image 4': 110, 'Image 5': 110,
    'Product URL': 220, 'Color': 95, 'Size': 95, 'SKU': 120,
    'Stock Status': 115, 'Stock Qty': 90, 'Offer': 150, 'Discount': 95,
    'Aliases': 170, 'Active': 80, 'Product ID': 150, 'Product Group ID': 160,
    'Variant ID': 160, 'Variant Name': 150, 'Updated At': 155
  };
  visibleHeaders.forEach((h, i) => sh.setColumnWidth(i + 1, widths[h] || 140));

  if (rowCount > 0) {
    const dataRange = sh.getRange(2, 1, rowCount, visibleCount);
    dataRange.setHorizontalAlignment('left');

    const priceCol = visibleHeaders.indexOf('Price') + 1;
    if (priceCol > 0) sh.getRange(2, priceCol, rowCount, 1).setHorizontalAlignment('right').setNumberFormat('#,##0.##');

    const qtyCol = visibleHeaders.indexOf('Stock Qty') + 1;
    if (qtyCol > 0) sh.getRange(2, qtyCol, rowCount, 1).setHorizontalAlignment('center').setNumberFormat('0');

    const centerHeaders = ['Currency', 'Product Image', 'Image 2', 'Image 3', 'Image 4', 'Image 5', 'Color', 'Size', 'SKU', 'Stock Status', 'Discount', 'Active', 'Product ID', 'Product Group ID', 'Variant ID', 'Updated At'];
    centerHeaders.forEach(h => {
      const c = visibleHeaders.indexOf(h) + 1;
      if (c > 0) sh.getRange(2, c, rowCount, 1).setHorizontalAlignment('center');
    });

    const stockCol = visibleHeaders.indexOf('Stock Status') + 1;
    if (stockCol > 0) {
      const rule = SpreadsheetApp.newDataValidation()
        .requireValueInList(['In Stock', 'Out of Stock', 'Preorder'], true)
        .setAllowInvalid(true)
        .build();
      sh.getRange(2, stockCol, rowCount, 1).setDataValidation(rule);
    }

    const activeCol = visibleHeaders.indexOf('Active') + 1;
    if (activeCol > 0) {
      try { sh.getRange(2, activeCol, rowCount, 1).insertCheckboxes(); } catch (_) {}
    }
  }

  try { sh.getRange(1, 1, lastRow, visibleCount).createFilter(); } catch (_) {}
}

function resolveImageSlotFromSnapshot_(sh, sheetRow, sourceIndices, rowValues, rowDisplays, rowFormulas, overGrid, resolvedIdx, idIdx, hashIdx) {
  const oldResolved = resolvedIdx >= 0 ? cleanUrl_(rowDisplays[resolvedIdx]) : '';
  const oldId = idIdx >= 0 ? cleanLine_(rowDisplays[idIdx]) : '';
  const oldHash = hashIdx >= 0 ? cleanLine_(rowDisplays[hashIdx]) : '';

  let url = '';
  let blob = null;

  for (const idx of sourceIndices) {
    if (!url) url = extractUrlFromSnapshotCell_(rowValues[idx], rowDisplays[idx], rowFormulas[idx]);
    if (!blob) {
      const over = overGrid.get(`${sheetRow}:${idx + 1}`);
      if (over) {
        try { blob = over.getBlob(); } catch (_) {}
      }
    }
    if (!blob) blob = blobFromCellImage_(rowValues[idx]);
  }

  if (url) {
    if (oldId) trashFile_(oldId);
    return { url, fileId: '', hash: '', managed: false };
  }

  if (blob) {
    const hash = blobHash_(blob);
    if (oldId && oldHash === hash && oldResolved) {
      return { url: oldResolved, fileId: oldId, hash, managed: true };
    }
    if (oldId) trashFile_(oldId);
    const ext = imageExtension_(blob.getContentType());
    blob.setName(`product-image-${sheetRow}-${Date.now()}.${ext}`);
    const file = DriveApp.createFile(blob);
    try { file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW); } catch (_) {}
    return { url: driveViewUrl_(file.getId()), fileId: file.getId(), hash, managed: true };
  }

  if (oldId) trashFile_(oldId);
  return { url: '', fileId: '', hash: '', managed: false };
}

function cleanupManagedImageFiles_(rows) {
  const props = PropertiesService.getScriptProperties();
  let previous = [];
  try { previous = JSON.parse(props.getProperty(IMAGE_REGISTRY_KEY) || '[]'); } catch (_) { previous = []; }
  const current = [];
  rows.forEach(row => row._imageMeta.forEach(m => {
    if (m && m.managed && m.fileId) current.push(m.fileId);
  }));
  const currentSet = new Set(current);
  previous.forEach(id => { if (id && !currentSet.has(id)) trashFile_(id); });
  props.setProperty(IMAGE_REGISTRY_KEY, JSON.stringify([...new Set(current)]));
}

function firstMeaningfulCell_(rowValues, rowDisplays, rowFormulas, indices) {
  for (const idx of indices) {
    const formula = String(rowFormulas[idx] || '').trim();
    const value = rowValues[idx];
    const display = rowDisplays[idx];
    if (formula && !/^=IMAGE\(/i.test(formula)) return display || formula;
    if (value !== '' && value !== null && value !== undefined && typeof value !== 'object') return value;
    if (cleanLine_(display)) return display;
  }
  return '';
}

function extractUrlFromSnapshotCell_(value, display, formula) {
  const f = String(formula || '').trim();
  const m = f.match(/^=IMAGE\(\s*["']([^"']+)["']/i);
  if (m) return cleanUrl_(m[1]);
  const d = cleanLine_(display);
  if (/^https?:\/\//i.test(d)) return cleanUrl_(d);
  if (typeof value === 'string' && /^https?:\/\//i.test(value.trim())) return cleanUrl_(value);
  return '';
}

function blobFromCellImage_(value) {
  if (!value || typeof value !== 'object') return null;
  if (typeof value.getContentUrl !== 'function') return null;
  try { return UrlFetchApp.fetch(value.getContentUrl()).getBlob(); } catch (_) { return null; }
}

function canonicalHeader_(raw) {
  const key = normalizeHeaderKey_(raw);
  return NORMALIZED_ALIAS_MAP[key] || '';
}

function normalizeHeaderKey_(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[৳₹$€£]/g, '')
    .replace(/[()\[\]{}._\-/:\\]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function cleanLine_(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/[\u00A0\t\r\n]+/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function cleanMultiline_(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map(line => line.replace(/[\u00A0\t]+/g, ' ').replace(/\s{2,}/g, ' ').trim())
    .filter(Boolean)
    .join('\n')
    .trim();
}

function cleanUrl_(value) {
  const s = cleanLine_(value);
  if (!s) return '';
  const m = s.match(/^=IMAGE\(\s*["']([^"']+)["']/i);
  const candidate = m ? m[1] : s;
  return /^https?:\/\//i.test(candidate) ? candidate.trim() : '';
}

function parseNumber_(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const s = String(value || '')
    .replace(/,/g, '')
    .replace(/[৳₹$€£]/g, '')
    .replace(/[^0-9.\-]/g, '');
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function parseInteger_(value) {
  const n = parseNumber_(value);
  return n === null ? null : Math.max(0, Math.round(n));
}

function parseBoolean_(value, defaultValue) {
  if (typeof value === 'boolean') return value;
  const s = cleanLine_(value).toLowerCase();
  if (!s) return defaultValue;
  if (['false', '0', 'no', 'off', 'inactive', 'disabled'].includes(s)) return false;
  if (['true', '1', 'yes', 'on', 'active', 'enabled'].includes(s)) return true;
  return defaultValue;
}

function normalizeStockStatus_(value) {
  const s = cleanLine_(value).toLowerCase();
  if (!s) return '';
  if (/out|sold|unavailable|নাই|শেষ/.test(s)) return 'Out of Stock';
  if (/pre.?order|advance|booking|প্রি.?অর্ডার/.test(s)) return 'Preorder';
  if (/in.?stock|available|yes|আছে|স্টক/.test(s)) return 'In Stock';
  return cleanLine_(value);
}

function normalizeUpdatedAt_(value) {
  if (value instanceof Date && !isNaN(value.getTime())) return value.toISOString();
  const s = cleanLine_(value);
  if (!s) return '';
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toISOString();
}

function latestDateText_(a, b) {
  if (!a) return b || '';
  if (!b) return a;
  const da = new Date(a), db = new Date(b);
  if (isNaN(da.getTime())) return b || a;
  if (isNaN(db.getTime())) return a;
  return db > da ? b : a;
}

function cleanKey_(value) {
  return cleanLine_(value).toLowerCase();
}

function normalizeNumberKey_(value) {
  return value === null || value === undefined || value === '' ? '' : String(Number(value));
}

function slugify_(value) {
  return cleanLine_(value)
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100);
}

function imageFormula_(url) {
  const escaped = String(url).replace(/"/g, '""');
  return `=IMAGE("${escaped}",4,72,72)`;
}

function imageExtension_(contentType) {
  const type = String(contentType || 'image/jpeg').toLowerCase();
  if (type.includes('png')) return 'png';
  if (type.includes('webp')) return 'webp';
  if (type.includes('gif')) return 'gif';
  return 'jpg';
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

function columnHasDataInArrays_(values, displays, idx) {
  for (let r = 0; r < displays.length; r++) {
    if (cleanLine_(displays[r][idx])) return true;
    const v = values[r][idx];
    if (v !== '' && v !== null && v !== undefined && typeof v === 'object') return true;
  }
  return false;
}
