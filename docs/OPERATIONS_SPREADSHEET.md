# Per-account Operations Spreadsheet

Step 04 ensures the following tabs exist for every active account:

- `Products`
- `FAQ`
- `Orders`
- `HumanSupportQueue`
- `HumanSupportLatest`
- `_System`

The merchant normally edits only `Products` and `FAQ`.

## Canonical Products columns

`Product ID | Product Name | Category | Subcategory | Price | Currency | Product Description | Product Image | Stock Status | Stock Qty | Color | Size | Offer | Discount | Aliases | Active | Updated At`

Legacy headers are recognized during catalog sync, including:

- `Product Name`
- `Price (৳)`
- `Product Description`
- `Product Image`
- `Stock Status`

Blank `Stock Status` means unknown; it must not be converted to out-of-stock.

If a recognized legacy Products sheet is detected, Step 05 first creates a timestamped `Products_BACKUP_...` tab, rewrites `Products` into the canonical columns, deduplicates exact repeated products, and sorts by Category/Subcategory/Product Name. It then syncs the canonical data into PostgreSQL. The workflow preserves factual values and never invents a price. Embedded Google Sheets images are not reliable API image URLs; put an explicit public/accessible image URL or Drive-backed URL in `Product Image`.

## HumanSupportQueue columns

`Conversation ID | Business ID | Business Name | Platform | Account ID | Customer ID | Customer External ID | Latest Customer Message | Latest Message Time | Conversation URL | Mode | Handoff Reason | Handoff Source | Status | Updated At`

One conversation should keep one queue row. `Mode=HUMAN` stops AI. Change it to `AI` and Step/production human-control sync resumes AI.

`HumanSupportLatest` is a newest-first view of the queue.
