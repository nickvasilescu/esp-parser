# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an ESP/SAGE promotional product presentation parser that extracts structured product data from PDF sell sheets. It uses Claude Opus 4.5 for PDF understanding and Orgo CUA (Computer Use Agent) for browser automation to download PDFs from vendor portals.

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Run orchestrator (main entry point)
python3 orchestrator.py <presentation_url>

# ESP presentation example
python3 orchestrator.py https://portal.mypromooffice.com/projects/500187876/presentations/500183020/products

# SAGE presentation example
python3 orchestrator.py https://www.viewpresentation.com/66907679185

# Test with single product (useful for debugging)
python3 orchestrator.py <url> --limit-products 1

# Skip CUA downloads (use existing PDFs)
python3 orchestrator.py <url> --skip-cua

# Full workflow with Zoho integration
python3 orchestrator.py <url> --zoho-upload --zoho-quote --calculator

# Parse single PDF directly (bypasses orchestrator)
python3 esp_parser.py -f product.pdf
python3 esp_parser.py -d ./pdfs/  # Process directory

# Run dashboard UI
cd dashboard-ui && npm run dev
```

## Architecture

### Data Flow

```
Presentation URL
       ↓
orchestrator.py (routes by URL domain)
       ↓
   ┌───┴───┐
   │       │
  ESP    SAGE
   │       │
   ↓       ↓
esp_presentation_downloader.py    sage_handler.py
(Orgo CUA downloads PDF)          (SAGE Connect API)
   ↓
esp_product_lookup.py
(CUA downloads each product's Distributor Report)
   ↓
pdf_processor.py + prompt.py / prompt_presentation.py
(Claude Opus 4.5 extracts JSON from PDFs)
   ↓
output_normalizer.py → unified_schema.py
(Converts ESP/SAGE output to unified format)
   ↓
Optional integrations:
- zoho_item_agent.py → Zoho Item Master
- zoho_quote_agent.py → Zoho Books quotes
- calculator_generator.py → Excel calculators
```

### Key Modules

- **orchestrator.py**: Main entry point, routes URLs to ESP or SAGE pipelines, manages job state
- **pdf_processor.py**: Generic PDF→JSON extraction using Claude, supports swappable prompts
- **prompt.py**: System prompt for extracting product sell sheet data (distributor reports)
- **prompt_presentation.py**: System prompt for extracting presentation overview (product list with sell prices)
- **unified_schema.py**: Dataclass definitions for normalized output format
- **output_normalizer.py**: Transforms ESP/SAGE output to unified schema
- **esp_presentation_downloader.py**: Orgo CUA agent for downloading presentation PDF
- **esp_product_lookup.py**: Orgo CUA agent for ESP+ login and product lookup
- **job_state.py**: Tracks workflow status for dashboard visualization
- **config.py**: Environment variable loading and validation

### Pricing Data Sources (Critical)

The system merges two pricing sources:
- **sell_price**: From presentation PDF (what customer sees) - parsed via `prompt_presentation.py`
- **net_cost**: From distributor report PDF (what distributor pays) - parsed via `prompt.py`

Products are matched by CPN (Customer Product Number) during merge in `orchestrator.py:merge_presentation_and_product_data()`.

## Environment Variables

Required:
- `ANTHROPIC_API_KEY`: Claude API key
- `ORGO_API_KEY`: Orgo CUA API key (for ESP pipeline)
- `ORGO_COMPUTER_ID`: Orgo VM instance ID
- `ESP_PLUS_EMAIL`: ESP+ portal login
- `ESP_PLUS_PASSWORD`: ESP+ portal password

Optional:
- `ZOHO_ORG_ID`, `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`: Zoho integration
- `SAGE_API_KEY`, `SAGE_API_SECRET`: SAGE Connect API (if available)

## Output Structure

All pipelines produce output in the unified schema format:
- `metadata`: Source info, timestamps, counts
- `client`/`presenter`: Contact information
- `products[]`: Array of normalized products with:
  - `identifiers`: CPN, vendor_sku, MPN
  - `item`: Name, description, materials, dimensions
  - `vendor`: Name, website (primary match key for Zoho), ASI/SAGE ID
  - `pricing.breaks[]`: quantity, sell_price, net_cost, catalog_price
  - `fees[]`: Setup, reorder, rush charges
  - `decoration`: Methods, locations, imprint areas

Output files saved to `output/` directory.
