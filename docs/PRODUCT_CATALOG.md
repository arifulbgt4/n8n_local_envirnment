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
