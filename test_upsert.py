import sys
sys.path.insert(0, 'src')
import json
from promo_parser.integrations.zoho.client import ZohoClient, ZohoAPIError
from promo_parser.integrations.zoho.transformer import build_item_payload, get_vendor_sku

# Load unified output
with open('/opt/promo-pipeline/output/unified_output_esp_20260107_195308.json') as f:
    data = json.load(f)

product = data['products'][0]
client = ZohoClient()

# Build payload like the real agent does
payload = build_item_payload(
    product=product,
    client_account_number="10050",
    discovered_fields={},  # Empty for now
    variation=None,
    category_id=None,
    presentation_url=None
)

print(f"SKU: {payload.get('sku')}")
print(f"Name: {payload.get('name')}")
print(f"Trying upsert...")

try:
    result = client.upsert_item(payload)
    print(f"\nSUCCESS!")
    print(f"  item_id: {result.get('item_id')}")
except ZohoAPIError as e:
    print(f"\nFAILED!")
    print(f"  Error: {e.message}")
    print(f"  Status: {e.status_code}")
    print(f"  Response: {json.dumps(e.response, indent=2) if e.response else 'None'}")
except Exception as e:
    print(f"\nEXCEPTION: {type(e).__name__}: {e}")
