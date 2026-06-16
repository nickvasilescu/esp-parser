# ESP PDF Parser

A Python CLI tool that uses Claude Opus 4.5 to extract structured product data from ESP+ promotional product sell sheets.

## Features

- **PDF Processing**: Directly processes PDF files using Claude's native document understanding
- **Structured Output**: Extracts data into a strict JSON schema with vendor info, pricing, decoration details, and more
- **Flexible Input**: Process single files or batch process entire directories
- **Multiple Output Modes**: Print to stdout, save to JSON files, or both
- **Robust Error Handling**: Graceful handling of API errors and malformed responses

## Requirements

- Python 3.8+
- Anthropic API key with access to Claude Opus 4.5

## Installation

1. Clone or download this directory:

```bash
cd esp-pdf-parser
```

2. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up your API key:

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

Or create a `.env` file in the project directory:

```
ANTHROPIC_API_KEY=your-api-key-here
```

## Usage

### Single File Processing

```bash
# Output to both stdout and JSON file
python esp_parser.py -f product.pdf

# Output to stdout only
python esp_parser.py -f product.pdf -o stdout

# Output to file only
python esp_parser.py -f product.pdf -o file

# Save to custom output directory
python esp_parser.py -f product.pdf -o file --output-dir ./output/
```

### Batch Directory Processing

```bash
# Process all PDFs in a directory
python esp_parser.py -d ./pdfs/

# Save all outputs to a specific directory
python esp_parser.py -d ./pdfs/ --output-dir ./output/

# Only print to stdout (no files)
python esp_parser.py -d ./pdfs/ -o stdout
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `-f, --file` | Path to a single PDF file to process |
| `-d, --directory` | Path to a directory containing PDF files |
| `-o, --output` | Output mode: `stdout`, `file`, or `both` (default: `both`) |
| `--output-dir` | Custom output directory for JSON files |

## Output Schema

The tool extracts product data into a comprehensive JSON schema with the following top-level sections:

```json
{
  "vendor": { ... },      // Supplier information, contact details, FOB points
  "item": { ... },        // Product identity, dimensions, materials, colors
  "variants": [ ... ],    // Color/size options for products and kit components
  "pricing": { ... },     // Price breaks, codes, validity dates
  "fees": [ ... ],        // Setup, reorder, proof, rush charges
  "decoration": { ... },  // Imprint methods, locations, sizes, color options
  "flags": { ... },       // Metadata (kit detection, source format)
  "raw_notes": { ... }    // Packaging, lead time, disclaimers
}
```

See `prompt.py` for the complete schema documentation.

## Example Output

```json
{
  "vendor": {
    "name": "Prime Line",
    "asi": "79530",
    "line_name": null,
    "contact_name": null,
    "address": {
      "city": "New Kensington",
      "state": "PA",
      "postal_code": "15068",
      "country": "USA"
    },
    "phones": ["800-555-1234"],
    "emails": ["orders@primeline.com"],
    "fob_points": [...]
  },
  "item": {
    "vendor_sku": "PL-1234",
    "name": "Custom Water Bottle",
    "description_short": "27 oz Tritan water bottle with custom imprint area.",
    "materials": ["Tritan Plastic"],
    "dimensions": {
      "length": 3.5,
      "width": 3.5,
      "height": 10.5,
      "unit": "in"
    }
  },
  "pricing": {
    "currency": "USD",
    "breaks": [
      {"min_qty": 48, "catalog_price": 12.99, "net_cost": 7.79},
      {"min_qty": 144, "catalog_price": 11.49, "net_cost": 6.89}
    ]
  }
}
```

## Error Handling

The tool handles various error scenarios:

- **Missing API Key**: Provides clear instructions for setting the environment variable
- **File Not Found**: Reports missing PDF files with the path
- **API Errors**: Catches and reports Anthropic API errors
- **JSON Parse Errors**: Handles cases where the model response isn't valid JSON
- **Batch Processing**: Continues processing remaining files if one fails

## Notes

- The tool uses Claude Opus 4.5 (`claude-opus-4-5-20251101`) for maximum accuracy
- PDF processing uses base64 encoding for API transmission
- Output JSON files are named with the same base name as the input PDF
- Progress messages are printed to stderr, JSON output to stdout

## License

MIT License

# esp-parser
