# Product catalog, variants, images, and deletion reconciliation

The `Products` sheet is the source of truth.

## Variants

Use `Product Group ID` for the parent product and `Variant ID` for a sellable color/size/style variant. Legacy repeated rows are consolidated by variant. Different colors/sizes remain separate variants. Unknown legacy columns are preserved in `Attributes JSON`; a deterministic `Product Summary` is generated when missing.

## Images

`Product Image` and `Image 2..5` accept HTTPS URLs or `=IMAGE("https://...")`.

For images inserted directly into Google Sheets cells or over the grid, bind `integrations/google-apps-script/PRODUCT_IMAGE_SYNC.gs` to the Operations Spreadsheet and run `installProductImageSyncTriggers()` once. It writes durable URLs into `Resolved Image 1..5`, stores Drive file IDs/hashes in technical columns, and trashes old Drive copies when an image is replaced or deleted.

If a Google Workspace policy blocks `ANYONE_WITH_LINK`, Meta cannot fetch a Drive-hosted image. Use public CDN/storage URLs instead.

## Deletion reconciliation

Every catalog sync builds the complete current variant ID set. A product/variant row removed from the sheet is hard-deleted from `products`; `product_media` cascades. `order_items.product_id` is `ON DELETE SET NULL`, preserving historical order rows.

For a product still present, its `product_media` rows are replaced from the current sheet image set in the same SQL statement. Removing an image therefore removes it from PostgreSQL on the next sync. The legacy `products.image_url` column keeps only the first current image for compatibility.

## Merchant-facing sheet layout

The `Products` tab must remain readable for a shop owner. Existing product sheets are **not destructively rewritten or reordered** during catalog sync. The sync accepts common English/Bangla header aliases and normalizes them in memory before PostgreSQL is updated.

For a newly-created sheet, the visible columns are intentionally compact: `Product Name`, `Price`, `Product Description`, `Product Image`, `Stock Status`, `Stock Qty`, `Category`, `Subcategory`, `Color`, `Size`, `SKU`, `Product URL`, `Offer`, `Discount`, `Aliases`, `Active`, `Updated At`.

Direct-image helper columns (`Resolved Image ...`, `_Image File ID ...`, `_Image Hash ...`) are internal implementation details. The Apps Script creates them when required and hides them automatically. Old empty `Image 2..5` columns are hidden as well; if the merchant actually puts data in one, it stays visible. Do not infer or write fake Color/Size values back into the merchant sheet; those fields are used only when explicitly supplied.
