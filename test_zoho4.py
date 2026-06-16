import sys
sys.path.insert(0, 'src')
from promo_parser.integrations.zoho.client import ZohoClient

client = ZohoClient()
item = client.get_item_by_sku("10050-14184667")

if item:
    print(f"Item: {item.get('name')}")
    print(f"SKU: {item.get('sku')}")
    print(f"\nCustom Fields:")
    for cf in item.get('custom_fields', []):
        label = cf.get('label', '')
        value = cf.get('value', '')
        if value:  # Only show fields with values
            print(f"  {label}: {value}")
else:
    print("Not found")
