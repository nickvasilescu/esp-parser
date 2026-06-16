import sys
sys.path.insert(0, 'src')
from promo_parser.integrations.zoho.client import ZohoClient

client = ZohoClient()
sku = "10050-14184667"

print(f"Searching for SKU: {sku}")
item = client.get_item_by_sku(sku)

if item:
    print(f"\nFOUND!")
    print(f"  item_id: {item.get('item_id')}")
    print(f"  name: {item.get('name')}")
    print(f"  sku: {item.get('sku')}")
else:
    print("\nNOT FOUND - this would cause CREATE instead of UPDATE")
