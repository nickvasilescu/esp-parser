import sys
sys.path.insert(0, 'src')
import json
from promo_parser.integrations.zoho.client import ZohoClient
from promo_parser.integrations.zoho.config import CUSTOM_FIELD_PATTERNS

client = ZohoClient()

# Discover custom fields like the agent does
discovered = client.discover_custom_fields(CUSTOM_FIELD_PATTERNS)

print(f"Total patterns: {len(CUSTOM_FIELD_PATTERNS)}")
print(f"Discovered fields: {len(discovered)}")
print("\nFields found:")
for key, field_id in discovered.items():
    print(f"  {key}: {field_id}")

# Check specifically for vendor_website
if "vendor_website" in discovered:
    print(f"\nvendor_website field found: {discovered['vendor_website']}")
else:
    print("\nvendor_website field NOT FOUND in Zoho (pattern won't match)")
    print("  Looking for: 'Item Mfg Web Address' or similar")
