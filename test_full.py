import sys
sys.path.insert(0, 'src')
import json
from promo_parser.integrations.zoho.client import ZohoClient, ZohoAPIError
from promo_parser.integrations.zoho.transformer import build_item_payload, map_custom_fields, extract_vendor_website
from promo_parser.integrations.zoho.config import CUSTOM_FIELD_PATTERNS

# Load unified output
with open('/opt/promo-pipeline/output/unified_output_esp_20260107_195308.json') as f:
    data = json.load(f)

product = data['products'][0]
vendor = product.get('vendor', {})
client = ZohoClient()

# Discover custom fields
discovered = client.discover_custom_fields(CUSTOM_FIELD_PATTERNS)
print(f"Discovered {len([v for v in discovered.values() if v])} custom fields with IDs")

# Test vendor_website extraction
website = extract_vendor_website(vendor)
print(f"\nVendor email: {vendor.get('email')}")
print(f"Vendor website (direct): {vendor.get('website')}")
print(f"extract_vendor_website(): {website}")

# Build full payload with custom fields
payload = build_item_payload(
    product=product,
    client_account_number="10050",
    discovered_fields=discovered,
    variation=None,
    category_id=None,
    presentation_url="https://portal.mypromooffice.com/test"
)

print(f"\nPayload SKU: {payload.get('sku')}")
print(f"Custom fields in payload: {len(payload.get('custom_fields', []))}")

# Check if vendor_website is in custom fields
for cf in payload.get('custom_fields', []):
    if cf.get('customfield_id') == discovered.get('vendor_website'):
        print(f"vendor_website value: {cf.get('value')}")

# Try upsert
print("\nTrying upsert with custom fields...")
try:
    result = client.upsert_item(payload)
    print(f"SUCCESS! item_id: {result.get('item_id')}")
    
    # Verify the custom field was set
    item = client.get_item_by_sku(payload['sku'])
    for cf in item.get('custom_fields', []):
        if 'mfg' in cf.get('label', '').lower() or 'web' in cf.get('label', '').lower():
            print(f"  {cf.get('label')}: {cf.get('value')}")
except ZohoAPIError as e:
    print(f"FAILED: {e.message}")
    if e.response:
        print(f"Response: {json.dumps(e.response, indent=2)}")
