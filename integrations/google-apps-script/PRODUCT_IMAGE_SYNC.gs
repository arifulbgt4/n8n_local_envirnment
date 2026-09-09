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
const SCRIPT_VERSION = '4.2-products-v5-grid-borders';
const BACKUP_RECOVERY_KEY = 'PRODUCT_BACKUP_RECOVERY_DONE_V4';
const IMAGE_REGISTRY_KEY = 'PRODUCT_IMAGE_FILE_REGISTRY_V3';

const PRODUCT_COLUMNS = [
  'Product ID',
  'Product Name',
  'Category',
  'Subcategory',
  'Price',
  'Currency',
  'Stock Qty',
  'Stock Status',
  'Color',
  'Size',
  'SKU',
  'Product Description',
  'Product Image',
  'Image 2',
  'Image 3',
  'Image 4',
  'Image 5',
  'Product URL',
  'Offer',
  'Discount',
  'Aliases',
  'Active',
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
  const ss = SpreadsheetApp.getActive();
  const sh = ss.getSheetByName(PRODUCT_SHEET);
  if (!sh) return;

  const lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) return;

  try {
    ensureOneTimeBackup_(sh);

    const current = snapshotProducts_(sh);
    let source = current;
    let recovered = false;
    const props = PropertiesService.getScriptProperties();

    if (props.getProperty(BACKUP_RECOVERY_KEY) !== 'true') {
      const backup = findOriginalProductsBackup_(ss);
      if (backup) {
        const backupSnapshot = snapshotProducts_(backup);
        const currentImages = countSnapshotImages_(current);
        const backupImages = countSnapshotImages_(backupSnapshot);
        const currentRich = snapshotRichness_(current);
        const backupRich = snapshotRichness_(backupSnapshot);

        if (
          (currentImages === 0 && backupImages > 0) ||
          (backupImages >= currentImages + 3 && backupRich > currentRich * 1.30) ||
          (current.rows.length < backupSnapshot.rows.length * 0.55 && backupImages > currentImages)
        ) {
          source = backupSnapshot;
          recovered = true;
        }
      }
    }

    const normalizedRows = source.rows.map(r => normalizeProductRow_(r, source.customHeaders));
    const mergedRows = consolidateDuplicateRows_(normalizedRows, source.customHeaders);
    finalizeIds_(mergedRows);
    rebuildProductsSheet_(sh, mergedRows, source.customHeaders);
    cleanupManagedImageFiles_(mergedRows);

    if (recovered) props.setProperty(BACKUP_RECOVERY_KEY, 'true');
    props.setProperty('PRODUCT_SHEET_SCHEMA_VERSION', SCRIPT_VERSION);
  } finally {
    lock.releaseLock();
  }
}

function recoverProductsFromBackupAndSync() {
  const ss = SpreadsheetApp.getActive();
  const sh = ss.getSheetByName(PRODUCT_SHEET);
  const backup = findOriginalProductsBackup_(ss);
  if (!sh) throw new Error('Products sheet not found.');
  if (!backup) throw new Error('No _Products_Backup_* sheet found.');

  const lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) throw new Error('Another Products sync is already running.');
  try {
    const source = snapshotProducts_(backup);
    const normalizedRows = source.rows.map(r => normalizeProductRow_(r, source.customHeaders));
    const mergedRows = consolidateDuplicateRows_(normalizedRows, source.customHeaders);
    finalizeIds_(mergedRows);
    rebuildProductsSheet_(sh, mergedRows, source.customHeaders);
    cleanupManagedImageFiles_(mergedRows);
    PropertiesService.getScriptProperties().setProperty(BACKUP_RECOVERY_KEY, 'true');
    PropertiesService.getScriptProperties().setProperty('PRODUCT_SHEET_SCHEMA_VERSION', SCRIPT_VERSION);
  } finally {
    lock.releaseLock();
  }
}

function findOriginalProductsBackup_(ss) {
  return ss.getSheets()
    .filter(s => /^_Products_Backup_/.test(s.getName()))
    .sort((a, b) => a.getName().localeCompare(b.getName()))[0] || null;
}

function countSnapshotImages_(snapshot) {
  return (snapshot.rows || []).reduce((n, r) => n + (r.images || []).filter(Boolean).length, 0);
}

function snapshotRichness_(snapshot) {
  return (snapshot.rows || []).reduce((score, r) => {
    const c = r.canonical || {};
    if (cleanMultiline_(c['Product Description'])) score += 2;
    if ((r.images || []).some(Boolean)) score += 3;
    if (cleanLine_(c['Category'])) score += 1;
    if (cleanLine_(c['Color']) || cleanLine_(c['Size']) || cleanLine_(c['SKU'])) score += 1;
    return score;
  }, 0);
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
  const explicitVariant = cleanKey_(row['Variant ID'] || row['SKU']);
  if (explicitVariant) return `variant:${explicitVariant}`;

  // Same name/price/color/size is one product. Differences in description
  // or images are merged into the same row instead of creating duplicates.
  return [
    cleanKey_(row['Product Name']),
    normalizeNumberKey_(row['Price']),
    cleanKey_(row['Color']),
    cleanKey_(row['Size'])
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
    let productId = cleanLine_(row['Product ID']);
    if (!productId) {
      const seed = [
        cleanKey_(row['Product Name']),
        normalizeNumberKey_(row['Price']),
        cleanKey_(row['Color']),
        cleanKey_(row['Size'])
      ].join('|');
      productId = `prd-${stableShortHash_(seed)}`;
    }

    const baseId = productId;
    let suffix = 2;
    while (seenProductIds.has(productId)) productId = `${baseId}-${suffix++}`;
    row['Product ID'] = productId;
    seenProductIds.add(productId);

    if (!cleanLine_(row['Product Group ID'])) row['Product Group ID'] = productId;

    const hasRealVariant = !!(
      cleanLine_(row['Variant ID']) || cleanLine_(row['SKU']) ||
      cleanLine_(row['Color']) || cleanLine_(row['Size']) || cleanLine_(row['Variant Name'])
    );
    if (hasRealVariant && !cleanLine_(row['Variant ID'])) {
      const variantSeed = [
        productId,
        cleanKey_(row['SKU']),
        cleanKey_(row['Color']),
        cleanKey_(row['Size']),
        cleanKey_(row['Variant Name'])
      ].join('|');
      row['Variant ID'] = `var-${stableShortHash_(variantSeed)}`;
    }
    if (!hasRealVariant) row['Variant ID'] = '';

    if (!row['Updated At']) row['Updated At'] = new Date().toISOString();
  });
}

function stableShortHash_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(text || ''))
    .map(b => (b + 256) % 256)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 12);
}

function rebuildProductsSheet_(sh, rows, customHeaders) {
  // Keep unknown custom data internally, but the merchant-facing canonical
  // DB-aligned columns must always be contiguous and visible.
  const visibleHeaders = [...PRODUCT_COLUMNS];
  const allHeaders = [...visibleHeaders, ...TECHNICAL_HEADERS];
  const requiredCols = allHeaders.length;
  const requiredRows = Math.max(2, rows.length + 1);

  try { const f = sh.getFilter(); if (f) f.remove(); } catch (_) {}
  try { sh.showColumns(1, sh.getMaxColumns()); } catch (_) {}
  try { sh.showRows(1, sh.getMaxRows()); } catch (_) {}

  if (sh.getMaxColumns() < requiredCols) {
    sh.insertColumnsAfter(sh.getMaxColumns(), requiredCols - sh.getMaxColumns());
  } else if (sh.getMaxColumns() > requiredCols) {
    sh.deleteColumns(requiredCols + 1, sh.getMaxColumns() - requiredCols);
  }
  if (sh.getMaxRows() < requiredRows) {
    sh.insertRowsAfter(sh.getMaxRows(), requiredRows - sh.getMaxRows());
  }

  sh.clear({contentsOnly:false});
  sh.getRange(1, 1, 1, requiredCols).setValues([allHeaders]);

  if (rows.length) {
    const data = rows.map(row => {
      const visible = PRODUCT_COLUMNS.map(h => {
        const imageIndex = IMAGE_HEADERS.indexOf(h);
        if (imageIndex >= 0) {
          const url = row._images[imageIndex] || '';
          return url ? imageFormula_(url) : '';
        }
        const v = row[h];
        return v === null || v === undefined ? '' : v;
      });

      const technical = [];
      for (let i = 0; i < 5; i++) technical.push(row._images[i] || '');
      for (let i = 0; i < 5; i++) technical.push(row._imageMeta[i]?.fileId || '');
      for (let i = 0; i < 5; i++) technical.push(row._imageMeta[i]?.hash || '');
      return [...visible, ...technical];
    });
    sh.getRange(2, 1, data.length, requiredCols).setValues(data);
  }

  formatProductsSheet_(sh, visibleHeaders, rows.length);
  try { sh.showColumns(1, PRODUCT_COLUMNS.length); } catch (_) {}
  try { sh.hideColumns(PRODUCT_COLUMNS.length + 1, TECHNICAL_HEADERS.length); } catch (_) {}
}

function formatProductsSheet_(sh, visibleHeaders, rowCount) {
  const visibleCount = PRODUCT_COLUMNS.length;
  const lastRow = Math.max(1, rowCount + 1);
  const range = sh.getRange(1, 1, lastRow, visibleCount);

  // Remove every old background/color/layout artifact.
  range
    .setBackground('#ffffff')
    .setFontColor('#202124')
    .setFontFamily('Arial')
    .setFontSize(10)
    .setVerticalAlignment('middle')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);

  // Permanent light grid borders for merchant-facing rows and columns.
  range.setBorder(
    true, true, true, true, true, true,
    '#dadce0',
    SpreadsheetApp.BorderStyle.SOLID
  );
  try { sh.setHiddenGridlines(false); } catch (_) {}

  const header = sh.getRange(1, 1, 1, visibleCount);
  header
    .setBackground('#ffffff')
    .setFontColor('#202124')
    .setFontWeight('bold')
    .setFontSize(10)
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle')
    .setBorder(true, true, true, true, true, true, '#dadce0', SpreadsheetApp.BorderStyle.SOLID)
    .setBorder(null, null, true, null, null, null, '#9aa0a6', SpreadsheetApp.BorderStyle.SOLID_MEDIUM);

  try { sh.setFrozenRows(1); sh.setFrozenColumns(2); } catch (_) {}
  sh.setRowHeight(1, 32);
  if (rowCount > 0) {
    sh.setRowHeights(2, rowCount, 82);
    sh.getRange(2, 1, rowCount, visibleCount).setBackground('#ffffff');
  }

  const widths = {
    'Product ID':130,'Product Name':220,'Category':120,'Subcategory':130,
    'Price':90,'Currency':75,'Stock Qty':85,'Stock Status':105,'Color':90,'Size':90,'SKU':120,
    'Product Description':360,'Product Image':110,'Image 2':110,'Image 3':110,'Image 4':110,'Image 5':110,
    'Product URL':220,'Offer':160,'Discount':90,'Aliases':180,'Active':70,
    'Product Group ID':140,'Variant ID':140,'Variant Name':140,'Updated At':160
  };
  PRODUCT_COLUMNS.forEach((h, i) => sh.setColumnWidth(i + 1, widths[h] || 120));

  if (rowCount > 0) {
    const priceCol = PRODUCT_COLUMNS.indexOf('Price') + 1;
    sh.getRange(2, priceCol, rowCount, 1).setNumberFormat('#,##0.##');
    const qtyCol = PRODUCT_COLUMNS.indexOf('Stock Qty') + 1;
    sh.getRange(2, qtyCol, rowCount, 1).setNumberFormat('0');

    const stockCol = PRODUCT_COLUMNS.indexOf('Stock Status') + 1;
    sh.getRange(2, stockCol, rowCount, 1).setDataValidation(
      SpreadsheetApp.newDataValidation()
        .requireValueInList(['In Stock', 'Out of Stock', 'Preorder'], true)
        .setAllowInvalid(true)
        .build()
    );

    const activeCol = PRODUCT_COLUMNS.indexOf('Active') + 1;
    sh.getRange(2, activeCol, rowCount, 1).setDataValidation(
      SpreadsheetApp.newDataValidation().requireCheckbox().build()
    );
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
    // After the first normalization a direct image becomes an IMAGE() formula
    // pointing at the durable Drive URL. Keep its managed file metadata instead
    // of trashing that same file on the next scheduled sync.
    if (oldId && oldResolved && url === oldResolved) {
      return { url, fileId: oldId, hash: oldHash, managed: true };
    }
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
  const current = [];
  rows.forEach(row => (row._imageMeta || []).forEach(m => {
    if (m && m.managed && m.fileId) current.push(m.fileId);
  }));
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
