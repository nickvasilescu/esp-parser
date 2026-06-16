# Zoho Item Master - Filled Examples from ESP & SAGE

## Example 1: ESP Product (Etched Wine Bottle)

**Client:** _(Client info from presentation - assume Account #10048)_

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ZOHO ITEM MASTER - NEW ITEM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Type:                    ● Goods    ○ Service                              │
│                                                                             │
│  Name:                    [Etched Cabernet Sauvignon Red Wine Bottle    ]   │
│                           ← item.name                                       │
│                                                                             │
│  SKU:                     [10048-100401                                 ]   │
│                           ← [ClientAcct#]-[identifiers.vendor_sku]          │
│                                                                             │
│  Unit:                    [Piece ▼]                                         │
│                           ← Default                                         │
│                                                                             │
│  Category:                [Beverages- Wine/champagne/liquor ▼]              │
│                           ← item.categories[0]                              │
│                                                                             │
│  Returnable Item:         ☐                                                 │
│                                                                             │
│  [Image placeholder - upload from presentation]                             │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Dimensions (L x W x H):  [    ] x [    ] x [    ] [in ▼]                   │
│                           ← item.dimensions (not available for this item)   │
│                                                                             │
│  Weight:                  [        ] [lb ▼]                                 │
│                           ← item.weight_value (not available)               │
│                                                                             │
│  Manufacturer:            [A Plus Wine Designs                          ]   │
│                           ← vendor.name                                     │
│                                                                             │
│  Brand:                   [                                             ]   │
│                           ← (not extracted)                                 │
│                                                                             │
│  UPC:                     [                                             ]   │
│                           ← (not extracted)                                 │
│                                                                             │
│  MPN:                     [100401                                       ]   │
│                           ← identifiers.mpn (SHOWS ON PURCHASE ORDERS)      │
│                                                                             │
│  EAN:                     [                                             ]   │
│                                                                             │
│  ISBN:                    [                                             ]   │
│                                                                             │
│  Sustainability:          [                                             ]   │
│  Recycled Content:        [   ] %                                           │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  SALES INFORMATION                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Sellable:                ☑                                                 │
│                                                                             │
│  Selling Price:           [62.63                ] USD                       │
│                           ← pricing.breaks[0].sell_price (qty 12 tier)      │
│                           ⚠️ QUESTION: Which qty tier? Lowest? All?         │
│                                                                             │
│  Account:                 [Sales ▼]                                         │
│                                                                             │
│  Description:             [750-milliliter cabernet sauvignon red wine   ]   │
│                           [bottle featuring deep hand etching with      ]   │
│                           [optional hand-painted color fills.           ]   │
│                           ← item.description_short                          │
│                                                                             │
│  Tax Preference:          ● Taxable    ○ Non-Taxable                        │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  PURCHASE INFORMATION                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Purchasable:             ☑                                                 │
│                                                                             │
│  Cost Price:              [37.578               ] USD                       │
│                           ← pricing.breaks[0].net_cost (qty 12 tier)        │
│                           ⚠️ QUESTION: Which qty tier to use?               │
│                                                                             │
│  Account:                 [Cost of Goods Sold ▼]                            │
│                                                                             │
│  Description:             [Consider a distinguished gift that speaks    ]   │
│                           [volumes of quality and craftsmanship...      ]   │
│                           ← item.description (full)                         │
│                                                                             │
│  Preferred Vendor:        [A Plus Wine Designs ▼]                           │
│                           ← vendor.name (MATCH BY vendor.website)           │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  INVENTORY                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Track Inventory:         ☐ (DISABLED per Koell)                            │
│                                                                             │
│  Inventory Account:       [─────────────]                                   │
│  Valuation Method:        [─────────────]                                   │
│  Reorder Point:           [─────────────]                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### ESP Source Data Used:

| Zoho Field           | Source Path                             | Value                                     |
| -------------------- | --------------------------------------- | ----------------------------------------- |
| Name                 | `item.name`                             | Etched Cabernet Sauvignon Red Wine Bottle |
| SKU                  | `[ClientAcct]-[identifiers.vendor_sku]` | 10048-100401                              |
| MPN                  | `identifiers.mpn`                       | 100401                                    |
| Category             | `item.categories[0]`                    | Beverages- Wine/champagne/liquor          |
| Manufacturer         | `vendor.name`                           | A Plus Wine Designs                       |
| Selling Price        | `pricing.breaks[0].sell_price`          | $62.63                                    |
| Cost Price           | `pricing.breaks[0].net_cost`            | $37.578                                   |
| Sales Description    | `item.description_short`                | 750-milliliter cabernet...                |
| Purchase Description | `item.description`                      | Consider a distinguished gift...          |
| Preferred Vendor     | Match by `vendor.website`               | apluswd.com → A Plus Wine Designs         |

### ESP Data NOT Mapped (needs decision):

| Data                  | Value                    | Question                            |
| --------------------- | ------------------------ | ----------------------------------- |
| `identifiers.cpn`     | 564949753                | Store in custom field?              |
| `vendor.asi`          | 30223                    | Store in custom field on vendor?    |
| `pricing.breaks[1-4]` | Other qty tiers          | How to store multiple price breaks? |
| `fees[0]`             | Setup: $156.25 / $125.00 | Separate line item? Custom field?   |
| `item.materials`      | Glass                    | Custom field?                       |
| `item.colors`         | Red                      | Custom field?                       |
| `shipping.lead_time`  | 5 business days          | Custom field?                       |

---

## Example 2: SAGE Product (Water Bottle)

**Client:** Cassadie Davis, Otava (Account #10052)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ZOHO ITEM MASTER - NEW ITEM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Type:                    ● Goods    ○ Service                              │
│                                                                             │
│  Name:                    [27 oz Tritan Wide Mouth Water Bottle         ]   │
│                           ← item.name                                       │
│                                                                             │
│  SKU:                     [10052-CE053                                  ]   │
│                           ← [ClientAcct#]-[identifiers.vendor_sku]          │
│                                                                             │
│  Unit:                    [Piece ▼]                                         │
│                           ← Default                                         │
│                                                                             │
│  Category:                [Bottles ▼]                                       │
│                           ← item.categories[0]                              │
│                                                                             │
│  Returnable Item:         ☐                                                 │
│                                                                             │
│  [Image: https://www.promoplace.com/ws/ws.dll/connect-pres-pic?...]         │
│  ← images[0]                                                                │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Dimensions (L x W x H):  [    ] x [3.89] x [8.27] [in ▼]                   │
│                           ← item.dimensions.raw: "8.2700" H x 3.8900" D"    │
│                           ⚠️ Need to parse from raw string                  │
│                                                                             │
│  Weight:                  [        ] [lb ▼]                                 │
│                           ← (not available)                                 │
│                                                                             │
│  Manufacturer:            [Prime Line®                                  ]   │
│                           ← vendor.name                                     │
│                                                                             │
│  Brand:                   [                                             ]   │
│                           ← (not extracted)                                 │
│                                                                             │
│  UPC:                     [                                             ]   │
│                           ← (not extracted)                                 │
│                                                                             │
│  MPN:                     [CE053                                        ]   │
│                           ← identifiers.mpn (SHOWS ON PURCHASE ORDERS)      │
│                                                                             │
│  EAN:                     [                                             ]   │
│                                                                             │
│  ISBN:                    [                                             ]   │
│                                                                             │
│  Sustainability:          [                                             ]   │
│  Recycled Content:        [   ] %                                           │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  SALES INFORMATION                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Sellable:                ☑                                                 │
│                                                                             │
│  Selling Price:           [8.43                 ] USD                       │
│                           ← pricing.breaks[0].sell_price (qty 48 tier)      │
│                           ⚠️ QUESTION: Which qty tier? Lowest? All?         │
│                                                                             │
│  Account:                 [Sales ▼]                                         │
│                                                                             │
│  Description:             [27 oz. water bottle crafted from durable     ]   │
│                           [BPA-Free Tritan Plastic...                   ]   │
│                           ← item.description (SAGE only has full desc)      │
│                                                                             │
│  Tax Preference:          ● Taxable    ○ Non-Taxable                        │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  PURCHASE INFORMATION                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Purchasable:             ☑                                                 │
│                                                                             │
│  Cost Price:              [5.06                 ] USD                       │
│                           ← pricing.breaks[0].net_cost (qty 48 tier)        │
│                           ⚠️ QUESTION: Which qty tier to use?               │
│                                                                             │
│  Account:                 [Cost of Goods Sold ▼]                            │
│                                                                             │
│  Description:             [27 oz. water bottle crafted from durable     ]   │
│                           [BPA-Free Tritan Plastic. Classic style...    ]   │
│                           ← item.description                                │
│                                                                             │
│  Preferred Vendor:        [Prime Line® ▼]                                   │
│                           ← vendor.name (MATCH BY vendor.website)           │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  INVENTORY                                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Track Inventory:         ☐ (DISABLED per Koell)                            │
│                                                                             │
│  Inventory Account:       [─────────────]                                   │
│  Valuation Method:        [─────────────]                                   │
│  Reorder Point:           [─────────────]                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### SAGE Source Data Used:

| Zoho Field       | Source Path                             | Value                                |
| ---------------- | --------------------------------------- | ------------------------------------ |
| Name             | `item.name`                             | 27 oz Tritan Wide Mouth Water Bottle |
| SKU              | `[ClientAcct]-[identifiers.vendor_sku]` | 10052-CE053                          |
| MPN              | `identifiers.mpn`                       | CE053                                |
| Category         | `item.categories[0]`                    | Bottles                              |
| Manufacturer     | `vendor.name`                           | Prime Line®                          |
| Dimensions       | `item.dimensions.raw`                   | 8.2700" H x 3.8900" D                |
| Selling Price    | `pricing.breaks[0].sell_price`          | $8.43                                |
| Cost Price       | `pricing.breaks[0].net_cost`            | $5.06                                |
| Description      | `item.description`                      | 27 oz. water bottle...               |
| Preferred Vendor | Match by `vendor.website`               | www.primeline.com → Prime Line®      |
| Image            | `images[0]`                             | https://www.promoplace.com/...       |

### SAGE Data NOT Mapped (needs decision):

| Data                      | Value                                    | Question                            |
| ------------------------- | ---------------------------------------- | ----------------------------------- |
| `identifiers.spc`         | MWGVW-GQXTS                              | Store in custom field?              |
| `vendor.sage_id`          | 53170                                    | Store in custom field on vendor?    |
| `pricing.breaks[1-4]`     | Other qty tiers                          | How to store multiple price breaks? |
| `fees[0]`                 | Setup: $57.50                            | Separate line item? Custom field?   |
| `fees[1]`                 | Reorder: $27.50                          | How to handle?                      |
| `item.colors`             | Black, Campus Purple, Classic Navy, etc. | Custom field?                       |
| `decoration.imprint_info` | Screen. 3.5" W x 4.5" H...               | Custom field?                       |

---

## Side-by-Side Comparison: ESP vs SAGE → Zoho

| Zoho Field          | ESP Source               | ESP Value           | SAGE Source            | SAGE Value             |
| ------------------- | ------------------------ | ------------------- | ---------------------- | ---------------------- |
| **Type**            | _(default)_              | Goods               | _(default)_            | Goods                  |
| **Name**            | `item.name`              | Etched Cabernet...  | `item.name`            | 27 oz Tritan...        |
| **SKU**             | `[Acct]-[vendor_sku]`    | 10048-100401        | `[Acct]-[vendor_sku]`  | 10052-CE053            |
| **Unit**            | _(default)_              | Piece               | _(default)_            | Piece                  |
| **Category**        | `item.categories[0]`     | Beverages- Wine...  | `item.categories[0]`   | Bottles                |
| **Dimensions**      | `item.dimensions`        | _(empty)_           | `item.dimensions.raw`  | 8.27" H x 3.89" D      |
| **Manufacturer**    | `vendor.name`            | A Plus Wine Designs | `vendor.name`          | Prime Line®            |
| **MPN**             | `identifiers.mpn`        | 100401              | `identifiers.mpn`      | CE053                  |
| **Selling Price**   | `breaks[0].sell_price`   | $62.63              | `breaks[0].sell_price` | $8.43                  |
| **Cost Price**      | `breaks[0].net_cost`     | $37.578             | `breaks[0].net_cost`   | $5.06                  |
| **Sales Desc**      | `item.description_short` | 750-milliliter...   | `item.description`     | 27 oz. water bottle... |
| **Purchase Desc**   | `item.description`       | Consider a...       | `item.description`     | 27 oz. water bottle... |
| **Pref Vendor**     | Match `vendor.website`   | A Plus Wine Designs | Match `vendor.website` | Prime Line®            |
| **Track Inventory** | _(default)_              | ☐ Disabled          | _(default)_            | ☐ Disabled             |
| **Taxable**         | _(default)_              | ☑ Yes               | _(default)_            | ☑ Yes                  |

---

## 🔴 CRITICAL QUESTIONS FOR KOELL

### 1. Price Breaks - How to handle multiple quantity tiers?

ESP has 5 price tiers:

```
Qty 12:  Sell $62.63, Cost $37.58, Margin $25.05
Qty 48:  Sell $57.50, Cost $34.50, Margin $23.00
Qty 108: Sell $53.68, Cost $32.21, Margin $21.47
Qty 204: Sell $50.93, Cost $30.56, Margin $20.37
Qty 300: Sell $49.00, Cost $29.40, Margin $19.60
```

**Options:**

- A) Use lowest qty tier (12) for Selling/Cost Price in Item Master
- B) Use minimum order qty as the default price
- C) Create Price Lists in Zoho with all tiers
- D) Store all tiers in custom fields
- E) Something else?

### 2. Fees - Where do setup charges go?

ESP Setup Fee: List $156.25, Net Cost $125.00
SAGE Setup Fee: List $57.50

**Options:**

- A) Custom field on Item Master for "Setup Fee"
- B) Separate line item when creating quotes
- C) Notes field
- D) Don't store in Item Master, add manually to quotes

### 3. Colors - How to store?

ESP: `['Red']`
SAGE: `['Black', 'Campus Purple', 'Classic Navy', 'Classic Red', 'Safety Yellow', 'True Royal', 'White']`

**Options:**

- A) Custom field "Available Colors" (comma-separated)
- B) Don't store, reference from source system
- C) Create variant items for each color

### 4. Lead Time / Production Time

ESP: `5 business days`
SAGE: `Normal production time is 5-7 working days`

**Options:**

- A) Custom field "Lead Time"
- B) Include in description
- C) Don't store in Item Master

### 5. Platform-Specific IDs

ESP has: `cpn` (564949753), `asi` (30223)
SAGE has: `spc` (MWGVW-GQXTS), `sage_id` (53170)

**Options:**

- A) Custom fields for each: ESP CPN, ASI, SAGE SPC, SAGE ID
- B) Single "Source ID" field with prefix (ESP:564949753 or SAGE:MWGVW-GQXTS)
- C) Don't store, rely on SKU for lookups

### 6. Imprint/Decoration Info

SAGE: `Screen. 3.5" W x 4.5" H; Standard Side imprint area. 7" W x 4.5" H; Wrap around second imprint area.`
ESP: Methods: `['Deep Etch']`, Colors: `1, 2, or 3 color options`

**Options:**

- A) Custom field "Imprint Info" (free text)
- B) Multiple custom fields (Method, Size, Location)
- C) Include in item description
- D) Don't store in Item Master

---

## Recommended Custom Fields for Zoho Item Master

Based on the available data, here are suggested custom fields:

| Custom Field Name     | Type              | Purpose                    |
| --------------------- | ----------------- | -------------------------- |
| `Setup Fee (List)`    | Currency          | Client-facing setup charge |
| `Setup Fee (Net)`     | Currency          | Distributor setup cost     |
| `Lead Time`           | Text              | Production/delivery time   |
| `Available Colors`    | Text/Multi-select | Product color options      |
| `Imprint Info`        | Text Area         | Decoration details         |
| `Source Platform`     | Dropdown          | ESP / SAGE                 |
| `Source ID`           | Text              | CPN (ESP) or SPC (SAGE)    |
| `ASI Number`          | Text              | Vendor ASI (ESP)           |
| `SAGE ID`             | Text              | Vendor SAGE ID             |
| `Price Valid Through` | Date              | Pricing expiration         |
| `Materials`           | Text              | Product materials          |

---

_Please review and provide feedback on these mappings and questions!_
