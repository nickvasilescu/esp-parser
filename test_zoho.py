import sys
sys.path.insert(0, 'src')
from promo_parser.integrations.zoho.client import ZohoClient

client = ZohoClient()
sku = "10050-S22C"
item = client.get_item_by_sku(sku)

if item:
    print(f"Item found: {item.get('item_id')}")
    print(f"Name: {item.get('name')}")
    # Check custom fields
    cfs = item.get('custom_fields', [])
    for cf in cfs:
        if 'mfg' in cf.get('label', '').lower() or 'web' in cf.get('label', '').lower():
            print(f"  {cf.get('label')}: {cf.get('value')}")
else:
    print("Item not found")
