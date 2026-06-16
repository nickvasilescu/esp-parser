import sys
sys.path.insert(0, 'src')
import json
from promo_parser.integrations.zoho.transformer import get_vendor_sku, build_item_name_sku

# Load the actual unified output from today's run
with open('/opt/promo-pipeline/output/unified_output_esp_20260107_195308.json') as f:
    data = json.load(f)

product = data['products'][0]
print(f"Source: {product.get('source')}")
print(f"Identifiers: {json.dumps(product.get('identifiers', {}), indent=2)}")

# Test what get_vendor_sku returns
sku = get_vendor_sku(product)
print(f"\nget_vendor_sku() returned: {sku}")

# Test what SKU would be built
full_sku = build_item_name_sku("10050", product)
print(f"build_item_name_sku() returned: {full_sku}")
