# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an ESP/SAGE promotional product presentation parser that extracts structured product data from PDF sell sheets. It uses Claude Opus 4.5 for PDF understanding and Orgo CUA (Computer Use Agent) for browser automation to download PDFs from vendor portals.

## Installation

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install package in development mode
pip install -e ".[dev]"
```

## Common Commands

```bash
# Run orchestrator (main entry point)
promo-parser <presentation_url>

# ESP presentation example
promo-parser https://portal.mypromooffice.com/projects/500187876/presentations/500183020/products

# SAGE presentation example
promo-parser https://www.viewpresentation.com/66907679185

# Test with single product (useful for debugging)
promo-parser <url> --limit-products 1

# Skip CUA downloads (use existing PDFs)
promo-parser <url> --skip-cua

# Full workflow with Zoho integration
promo-parser <url> --zoho-upload --zoho-quote --calculator

# Parse single PDF directly (bypasses orchestrator)
esp-parser -f product.pdf
esp-parser -d ./pdfs/  # Process directory

# Run tests
pytest tests/

# Run dashboard UI
cd frontend && npm run dev
```

## Package Structure

```
promo_parser/
├── pyproject.toml              # Package configuration
├── src/promo_parser/
│   ├── core/                   # Core infrastructure
│   │   ├── config.py           # Environment variable loading
│   │   ├── schema.py           # Unified output dataclasses
│   │   ├── state.py            # Job state tracking
│   │   └── normalizer.py       # ESP/SAGE → unified format
│   │
│   ├── extraction/             # PDF extraction
│   │   ├── processor.py        # Claude-powered PDF→JSON
│   │   ├── tools.py            # Agent tool definitions
│   │   └── prompts/
│   │       ├── product.py      # Distributor report prompt
│   │       └── presentation.py # Presentation overview prompt
│   │
│   ├── pipelines/
│   │   ├── orchestrator.py     # Main entry point
│   │   ├── esp/                # ESP pipeline
│   │   │   ├── downloader.py   # Orgo CUA for presentations
│   │   │   ├── lookup.py       # Orgo CUA for product lookup
│   │   │   ├── parser.py       # ESP PDF parser CLI
│   │   │   └── file_handler.py # Orgo file downloads
│   │   └── sage/               # SAGE pipeline
│   │       ├── handler.py      # SAGE Connect API
│   │       └── scraper.py      # Presentation scraper
│   │
│   └── integrations/
│       ├── zoho/               # Zoho Books integration
│       │   ├── config.py
│       │   ├── client.py
│       │   ├── transformer.py
│       │   ├── item_agent.py
│       │   └── quote_agent.py
│       └── calculator/
│           └── generator.py    # Excel calculator generation
│
├── tests/                      # Test suite
├── frontend/                   # Dashboard UI (Next.js)
└── output/                     # Runtime output (gitignored)
```

## Architecture

### Data Flow

```
Presentation URL
       ↓
Orchestrator (routes by URL domain)
       ↓
   ┌───┴───┐
   │       │
  ESP    SAGE
   │       │
   ↓       ↓
pipelines/esp/downloader.py      pipelines/sage/handler.py
(Orgo CUA downloads PDF)         (SAGE Connect API)
   ↓
pipelines/esp/lookup.py
(CUA downloads each product's Distributor Report)
   ↓
extraction/processor.py + prompts/{product,presentation}.py
(Claude Opus 4.5 extracts JSON from PDFs)
   ↓
core/normalizer.py → core/schema.py
(Converts ESP/SAGE output to unified format)
   ↓
Optional integrations:
- integrations/zoho/item_agent.py → Zoho Item Master
- integrations/zoho/quote_agent.py → Zoho Books quotes
- integrations/calculator/generator.py → Excel calculators
```

### Key Modules

- **pipelines/orchestrator.py**: Main entry point, routes URLs to ESP or SAGE pipelines, manages job state
- **extraction/processor.py**: Generic PDF→JSON extraction using Claude, supports swappable prompts
- **extraction/prompts/product.py**: System prompt for extracting product sell sheet data (distributor reports)
- **extraction/prompts/presentation.py**: System prompt for extracting presentation overview (product list with sell prices)
- **core/schema.py**: Dataclass definitions for normalized output format
- **core/normalizer.py**: Transforms ESP/SAGE output to unified schema
- **pipelines/esp/downloader.py**: Orgo CUA agent for downloading presentation PDF
- **pipelines/esp/lookup.py**: Orgo CUA agent for ESP+ login and product lookup
- **core/state.py**: Tracks workflow status for dashboard visualization
- **core/config.py**: Environment variable loading and validation

### Pricing Data Sources (Critical)

The system merges two pricing sources:
- **sell_price**: From presentation PDF (what customer sees) - parsed via `extraction/prompts/presentation.py`
- **net_cost**: From distributor report PDF (what distributor pays) - parsed via `extraction/prompts/product.py`

Products are matched by CPN (Customer Product Number) during merge in `pipelines/orchestrator.py:merge_presentation_and_product_data()`.

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
