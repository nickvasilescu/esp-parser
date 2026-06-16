import sys
sys.path.insert(0, 'src')
from promo_parser.integrations.zoho.client import ZohoClient

client = ZohoClient()

# Search for items with 10050 in SKU
items = client._make_request("GET", "/items", params={"search_text": "10050", "per_page": 10})
print(f"Found {len(items.get('items', []))} items matching '10050':")
for item in items.get('items', [])[:5]:
    print(f"  SKU: {item.get('sku')} - {item.get('name')[:50]}")
