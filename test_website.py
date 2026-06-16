import sys
sys.path.insert(0, 'src')
from promo_parser.integrations.zoho.transformer import extract_vendor_website

# Test with the actual data from this run
vendor = {
    "website": None,
    "email": "customercare@leprechaunpromotions.com"
}

result = extract_vendor_website(vendor)
print(f"Input: email={vendor['email']}, website={vendor['website']}")
print(f"Output: {result}")
print(f"Expected: leprechaunpromotions.com")
print(f"Match: {'YES' if result == 'leprechaunpromotions.com' else 'NO'}")
