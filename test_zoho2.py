import sys
sys.path.insert(0, 'src')

# Import directly to avoid orchestrator import chain
import importlib.util
spec = importlib.util.spec_from_file_location("client", "src/promo_parser/integrations/zoho/client.py")
client_mod = importlib.util.module_from_spec(spec)
sys.modules["client"] = client_mod

# We need config too
spec2 = importlib.util.spec_from_file_location("config", "src/promo_parser/integrations/zoho/config.py")
config_mod = importlib.util.module_from_spec(spec2)
sys.modules["promo_parser.integrations.zoho.config"] = config_mod
spec2.loader.exec_module(config_mod)

spec.loader.exec_module(client_mod)

ZohoClient = client_mod.ZohoClient
client = ZohoClient()
sku = "10050-S22C"
item = client.get_item_by_sku(sku)

if item:
    print(f"Item found: {item.get('item_id')}")
    print(f"Name: {item.get('name')}")
    cfs = item.get('custom_fields', [])
    for cf in cfs:
        label = cf.get('label', '').lower()
        if 'mfg' in label or 'web' in label or 'vendor' in label:
            print(f"  {cf.get('label')}: {cf.get('value')}")
else:
    print("Item not found")
