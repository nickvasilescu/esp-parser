# Zoho Item Master Field Mapping - Questions for Koell

## Overview

We've built a system that extracts product data from both **ESP** and **SAGE** presentations and normalizes it into a unified format. Before we can push this data into Zoho Item Master, we need your input on exactly which fields should be mapped and how.

---

## SECTION 1: CORE IDENTIFIERS

These are the key fields that identify a product.

| Our Field                       | ESP Example | SAGE Example  | Description                      |
| ------------------------------- | ----------- | ------------- | -------------------------------- |
| `identifiers.mpn`               | `100401`    | `CE053`       | Manufacturer/Vendor Part Number  |
| `identifiers.vendor_sku`        | `100401`    | `CE053`       | Vendor's SKU (often same as MPN) |
| `identifiers.cpn`               | `564949753` | _(n/a)_       | ESP Customer Product Number      |
| `identifiers.spc`               | _(n/a)_     | `MWGVW-GQXTS` | SAGE Product Code                |
| `identifiers.internal_item_num` | _(n/a)_     | `CE053`       | SAGE Internal Item Number        |

### Questions:

1. **Zoho SKU Field**: We currently plan to format as `[ClientAccountNumber]-[vendor_sku]`

   - Example: `10048-100401` or `10048-CE053`
   - **Is this format correct?** Should it include anything else?

2. **Zoho MPN Field**: We plan to use `vendor_sku` or `mpn`

   - **Confirm this goes on Purchase Orders to vendors?**

3. **Should we store the ESP `cpn` or SAGE `spc` anywhere in Zoho?**
   - These are platform-specific product IDs
   - Could be useful for re-looking up products later

---

## SECTION 2: PRODUCT INFORMATION

| Our Field                | ESP Example                                                      | SAGE Example                                                          | Description        |
| ------------------------ | ---------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------ |
| `item.name`              | Etched Cabernet Sauvignon Red Wine Bottle                        | 27 oz Tritan Wide Mouth Water Bottle                                  | Product Name       |
| `item.description`       | _Consider a distinguished gift that speaks volumes..._           | _27 oz. water bottle crafted from durable BPA-Free Tritan Plastic..._ | Full Description   |
| `item.description_short` | _750-milliliter cabernet sauvignon red wine bottle featuring..._ | _(n/a)_                                                               | Short Description  |
| `item.categories`        | `['Beverages- Wine/champagne/liquor']`                           | `['Bottles']`                                                         | Product Categories |
| `item.colors`            | `['Red']`                                                        | `['Black', 'Campus Purple', 'Classic Navy', ...]`                     | Available Colors   |
| `item.materials`         | `['Glass']`                                                      | _(n/a)_                                                               | Materials          |
| `item.dimensions.raw`    | _(n/a)_                                                          | `8.2700" H x 3.8900" D`                                               | Dimensions         |

### Questions:

4. **Item Name in Zoho**: Use `item.name` directly?

   - Any character limits or formatting rules?

5. **Description**: Which field in Zoho should get the description?

   - Full description or short description?
   - Both?

6. **Categories**: ESP and SAGE have different category names

   - Do you have a master category list in Zoho these should map to?
   - Or create new categories as we encounter them?

7. **Colors**: Should all available colors be stored?

   - As a comma-separated list?
   - As a custom field?

8. **Materials/Dimensions**: Are these needed in Zoho?
   - If yes, which Zoho fields?

---

## SECTION 3: VENDOR INFORMATION

| Our Field          | ESP Example         | SAGE Example                      | Description                    |
| ------------------ | ------------------- | --------------------------------- | ------------------------------ |
| `vendor.name`      | A Plus Wine Designs | Prime Line®                       | Vendor Name                    |
| `vendor.website`   | `apluswd.com`       | `www.primeline.com`               | **Vendor Website (MATCH KEY)** |
| `vendor.asi`       | `30223`             | _(n/a)_                           | ASI Number                     |
| `vendor.sage_id`   | _(n/a)_             | `53170`                           | SAGE Supplier ID               |
| `vendor.email`     | `info@apluswd.com`  | `orders@primeline.com`            | Vendor Email                   |
| `vendor.phone`     | `(800) 201-9463`    | `877.858.9908`                    | Vendor Phone                   |
| `vendor.line_name` | _(n/a)_             | `Prime Line/Harriton/Columbia...` | Product Line Name              |

### Questions:

9. **Vendor Matching**: We plan to match vendors by **website URL** (not name) because vendor names vary

   - Example: "Hit Promo" vs "HIT Promotional Products" vs "Hit"
   - **Is website URL the right match key?**

10. **Vendor Group Field**: From our Dec 4 meeting, you mentioned tracking "We Promo" / "EQP Promo" membership

    - Where should this be stored in Zoho?
    - How do we determine which group a vendor belongs to?

11. **ASI vs SAGE ID**: Should we store both industry IDs?
    - If yes, which Zoho fields?

---

## SECTION 4: PRICING (Critical)

| Our Field               | ESP Example  | SAGE Example | Description         |
| ----------------------- | ------------ | ------------ | ------------------- |
| `pricing.price_code`    | `5R`         | `CCCCC`      | Price Code          |
| `pricing.currency`      | `USD`        | `USD`        | Currency            |
| `pricing.valid_through` | `2026-10-21` | _(n/a)_      | Price Valid Through |

### Price Breaks (Multiple per product):

| Field            | ESP Example | SAGE Example | Description                                 |
| ---------------- | ----------- | ------------ | ------------------------------------------- |
| `quantity`       | 12          | 48           | Quantity Tier                               |
| `sell_price`     | $62.63      | $8.43        | **Client-facing price** (from Presentation) |
| `net_cost`       | $37.578     | $5.06        | **Distributor cost** (from Report/API)      |
| `catalog_price`  | $62.63      | $8.43        | MSRP/List Price                             |
| `margin`         | $25.05      | $3.37        | Calculated: sell_price - net_cost           |
| `margin_percent` | 40.0%       | 39.98%       | Calculated margin percentage                |

### Questions:

12. **Price Break Storage**: Products have multiple price tiers (e.g., qty 12, 48, 108, 204, 300)

    - How should these be stored in Zoho?
    - Separate line items per qty tier?
    - Custom fields?
    - Price list?

13. **Which price goes where?**

    - `sell_price` → What the client pays
    - `net_cost` → What you pay the distributor
    - `catalog_price` → MSRP
    - **Which of these go into Zoho Item Master?**

14. **Margin**: Should we store calculated margin in Zoho?

    - Dollar amount?
    - Percentage?
    - Both?

15. **Price Rounding**: From Dec 4 meeting - "round down" for quantity tiers
    - Example: Order of 50 units gets the 48-unit price, not 96-unit price
    - **Is this handled in Zoho or in the calculator?**

---

## SECTION 5: FEES/CHARGES

| Our Field      | ESP Example   | SAGE Example | Description                                                                                           |
| -------------- | ------------- | ------------ | ----------------------------------------------------------------------------------------------------- |
| `fee_type`     | `setup`       | `setup`      | Type: setup, reorder, proof, pms_match, spec_sample, copy_change, additional_color, payment_surcharge |
| `name`         | Set-up Charge | Setup Charge | Fee Name                                                                                              |
| `list_price`   | $156.25       | $57.50       | Client-facing fee                                                                                     |
| `net_cost`     | $125.00       | _(n/a)_      | Distributor fee cost (ESP only)                                                                       |
| `charge_basis` | `per_order`   | _(n/a)_      | per_order, per_unit, percentage                                                                       |
| `price_code`   | `V`           | `G`          | Price Code                                                                                            |

### Common Fee Types:

- **setup** - Initial setup charge
- **reorder** - Repeat/reorder charge
- **proof** - Proof charge
- **pms_match** - PMS color matching
- **spec_sample** - Spec sample charge
- **copy_change** - Copy change charge
- **additional_color** - Extra imprint colors
- **payment_surcharge** - Credit card fee (usually 3%)

### Questions:

16. **Fee Storage**: How should fees be stored in Zoho?

    - As separate line items on quotes?
    - As custom fields on the item?
    - In a related fees table?

17. **Setup Fee**: This is the most common fee

    - Should it be a default field on each item?
    - Include both list_price AND net_cost?

18. **Net Cost for Fees**: ESP provides distributor cost for fees, SAGE doesn't
    - Should we estimate SAGE fee costs?
    - Or leave them blank for SAGE items?

---

## SECTION 6: DECORATION/IMPRINT INFO

| Our Field                        | ESP Example                   | SAGE Example                                             | Description                  |
| -------------------------------- | ----------------------------- | -------------------------------------------------------- | ---------------------------- |
| `decoration.methods`             | `['Deep Etch']`               | _(n/a)_                                                  | Available decoration methods |
| `decoration.imprint_info`        | _(n/a)_                       | `Screen. 3.5" W x 4.5" H; Standard Side imprint area...` | Imprint info string          |
| `decoration.sold_unimprinted`    | `false`                       | _(n/a)_                                                  | Can be sold blank?           |
| `decoration.imprint_colors_desc` | `1, 2, or 3 color options...` | _(n/a)_                                                  | Color options description    |

### Questions:

19. **Decoration Info**: How much imprint detail do you need in Zoho?

    - Just the method name (Screen, Embroidery, Laser, etc.)?
    - Full imprint area dimensions?
    - Store as structured data or free text?

20. **Imprint Areas**: ESP has structured location/area data, SAGE has a text string
    - Worth normalizing into a consistent format?
    - Or just store whatever we have as notes?

---

## SECTION 7: SHIPPING/LOGISTICS

| Our Field                    | ESP Example                  | SAGE Example                                 | Description          |
| ---------------------------- | ---------------------------- | -------------------------------------------- | -------------------- |
| `shipping.lead_time`         | `5 business days`            | `Normal production time is 5-7 working days` | Production/Lead Time |
| `shipping.ship_point`        | _(zip)_                      | _(zip)_                                      | Ship From Location   |
| `shipping.packaging`         | `See ordering guidelines...` | `Bulk. 48 units per carton...`               | Packaging Info       |
| `shipping.units_per_carton`  | _(n/a)_                      | `200`                                        | Units per carton     |
| `shipping.weight_per_carton` | _(n/a)_                      | `22 lbs`                                     | Carton weight        |

### Questions:

21. **Lead Time**: Critical for quotes - where does this go in Zoho?

    - Standard field?
    - Custom field?

22. **Packaging/Carton Info**: Needed in Zoho?
    - Useful for shipping cost estimates?

---

## SECTION 8: IMAGES

| Our Field | ESP Example           | SAGE Example                                                       |
| --------- | --------------------- | ------------------------------------------------------------------ |
| `images`  | _(not yet extracted)_ | `https://www.promoplace.com/ws/ws.dll/connect-pres-pic?acctid=...` |

### Questions:

23. **Product Images**: Should images be uploaded to Zoho?
    - Direct image upload?
    - Store URL reference?
    - Which image (primary from presentation)?

---

## SECTION 9: ZOHO DEFAULTS

Based on our Dec 2 meeting, please confirm these defaults:

| Setting         | Value        | Confirm? |
| --------------- | ------------ | -------- |
| Track Inventory | **Disabled** | ✓ / ✗    |
| Default Unit    | **Piece**    | ✓ / ✗    |
| Taxable         | **Yes**      | ✓ / ✗    |

### Questions:

24. **Any other default settings** we should apply to all items?

25. **Item Status**: Active/Inactive?
    - Default to Active?
    - Based on `pricing.valid_through` date?

---

## SECTION 10: CLIENT-SPECIFIC DATA

| Our Field        | ESP Example       | SAGE Example     | Description    |
| ---------------- | ----------------- | ---------------- | -------------- |
| `client.name`    | _(from metadata)_ | `Cassadie Davis` | Client Name    |
| `client.company` | _(from metadata)_ | `Otava`          | Client Company |

### Questions:

26. **Client Account Number**: Where do we get this from?
    - Manually input?
    - Lookup from Zoho contacts?
    - This is needed for the SKU format: `[AccountNumber]-[vendor_sku]`

---

## Summary: Key Decisions Needed

1. ☐ **SKU Format**: `[ClientAcct#]-[vendor_sku]` - correct?
2. ☐ **Vendor Match Key**: Website URL - correct?
3. ☐ **Price Break Storage**: How to handle multiple qty tiers?
4. ☐ **Fee Storage**: Line items, custom fields, or related table?
5. ☐ **Category Mapping**: Your list or create as we go?
6. ☐ **Which prices**: sell_price, net_cost, catalog_price, margin - which ones?
7. ☐ **Vendor Group Field**: Where and how?
8. ☐ **Image Handling**: Upload or URL reference?

---

_Please mark up this document or reply with your answers. We'll configure the Zoho integration based on your input!_
