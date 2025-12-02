#!/usr/bin/env python3
"""
ViewPresentation.com Scraper
============================
Uses SeleniumBase UC Mode to bypass bot detection, BeautifulSoup for parsing.

Usage:
    python scraper.py <url>
    python scraper.py https://www.viewpresentation.com/66907679185
"""

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from seleniumbase import SB


@dataclass
class PriceBreak:
    quantity: int
    price: float


@dataclass
class Product:
    title: str
    item_number: str
    description: str
    colors: list[str] = field(default_factory=list)
    decoration_info: Optional[str] = None
    price_breaks: list[PriceBreak] = field(default_factory=list)
    price_includes: Optional[str] = None
    additional_charges: Optional[str] = None
    dimensions: Optional[str] = None
    image_urls: list[str] = field(default_factory=list)


@dataclass
class Presentation:
    url: str
    title: Optional[str] = None
    client_name: Optional[str] = None
    client_company: Optional[str] = None
    presenter_name: Optional[str] = None
    presenter_company: Optional[str] = None
    presenter_phone: Optional[str] = None
    presenter_location: Optional[str] = None
    products: list[Product] = field(default_factory=list)


def scrape(url: str) -> Presentation:
    """Fetch page with SeleniumBase, parse with BeautifulSoup."""
    with SB(uc=True, headless=True) as sb:
        sb.open(url)
        sb.sleep(3)
        html = sb.get_page_source()
    
    soup = BeautifulSoup(html, "html.parser")
    return parse_page(url, soup)


def parse_page(url: str, soup: BeautifulSoup) -> Presentation:
    """Parse the entire page."""
    pres = Presentation(url=url)
    
    # Title
    h3 = soup.select_one("#intro h3")
    pres.title = h3.get_text(strip=True) if h3 else None
    
    # Client info
    client_lis = soup.select(".client-info.first li")
    if len(client_lis) >= 1:
        pres.client_name = client_lis[0].get_text(strip=True) or None
    if len(client_lis) >= 2:
        pres.client_company = client_lis[1].get_text(strip=True) or None
    
    # Presenter info from header-text paragraphs
    header_ps = soup.select(".header-text p")
    texts = [p.get_text(strip=True) for p in header_ps if p.get_text(strip=True)]
    if len(texts) >= 1:
        pres.presenter_name = texts[0]
    if len(texts) >= 2:
        pres.presenter_company = texts[1]
    if len(texts) >= 3:
        pres.presenter_phone = texts[2]
    if len(texts) >= 4:
        pres.presenter_location = texts[3]
    
    # Products
    for prod_elem in soup.select("div.product"):
        product = parse_product(url, prod_elem)
        if product:
            pres.products.append(product)
    
    return pres


def parse_product(base_url: str, elem) -> Optional[Product]:
    """Parse a single product element."""
    # Title
    title_elem = elem.select_one("p.title")
    if not title_elem:
        return None
    title = title_elem.get_text(strip=True)
    if not title:
        return None
    
    # Item number
    item_elem = elem.select_one("p.item")
    item_number = ""
    if item_elem:
        item_text = item_elem.get_text(strip=True)
        if "Item number:" in item_text:
            item_number = item_text.split("Item number:")[-1].strip()
    
    # Description - get text from the description div/span
    description = ""
    desc_container = elem.select_one("p.description")
    if desc_container:
        # Get the parent div which contains the actual text
        parent = desc_container.find_parent("div")
        if parent:
            description = parent.get_text(" ", strip=True)
    
    # Extract fields from p.additional elements
    colors = []
    decoration_info = None
    price_includes = None
    additional_charges = None
    
    for add_elem in elem.select("p.additional"):
        text = add_elem.get_text(" ", strip=True)
        if text.startswith("Colors:"):
            colors_text = text.split("Colors:", 1)[-1].strip()
            colors = [c.strip() for c in colors_text.split(",") if c.strip()]
        elif text.startswith("Decoration Information:"):
            decoration_info = text.split("Decoration Information:", 1)[-1].strip()
        elif text.startswith("Price Includes:"):
            price_includes = text.split("Price Includes:", 1)[-1].strip()
        elif text.startswith("Additional Charge Details:"):
            additional_charges = text.split("Additional Charge Details:", 1)[-1].strip()
    
    # Price breaks
    price_breaks = extract_price_breaks(elem)
    
    # Dimensions from description
    dimensions = extract_dimensions(description)
    
    # Images
    image_urls = []
    seen = set()
    for img in elem.select("[data-lightbox] img, .gallery img"):
        src = img.get("src")
        if src and src not in seen:
            image_urls.append(urljoin(base_url, src))
            seen.add(src)
    
    return Product(
        title=title,
        item_number=item_number,
        description=description,
        colors=colors,
        decoration_info=decoration_info,
        price_breaks=price_breaks,
        price_includes=price_includes,
        additional_charges=additional_charges,
        dimensions=dimensions,
        image_urls=image_urls,
    )


def extract_price_breaks(elem) -> list[PriceBreak]:
    """Extract quantity/price tiers from pricing table."""
    price_breaks = []
    
    # Get quantities from .price-qty-row
    qty_row = elem.select_one(".price-qty-row")
    if not qty_row:
        return []
    
    quantities = []
    for td in qty_row.select("td")[1:]:  # Skip "Qty" label
        style = td.get("style", "")
        if "display:none" in style or "display: none" in style:
            continue
        text = td.get_text(strip=True)
        if text:
            try:
                quantities.append(int(text.replace(",", "")))
            except ValueError:
                continue
    
    # Get prices from "Price" row
    table = elem.select_one(".price-grid")
    if not table:
        return []
    
    for row in table.select("tr"):
        cells = row.select("td")
        if not cells:
            continue
        first_cell_text = cells[0].get_text(strip=True)
        if first_cell_text == "Price":
            prices = []
            for td in cells[1:]:
                style = td.get("style", "")
                if "display:none" in style or "display: none" in style:
                    continue
                text = td.get_text(strip=True)
                if text:
                    try:
                        prices.append(float(text.replace("$", "").replace(",", "")))
                    except ValueError:
                        continue
            
            for qty, price in zip(quantities, prices):
                price_breaks.append(PriceBreak(quantity=qty, price=price))
            break
    
    return price_breaks


def extract_dimensions(description: str) -> Optional[str]:
    """Extract dimensions from description."""
    if not description:
        return None
    
    patterns = [
        r'(\d+[\d\s/\.]*"\s*[HWLD]?\s*[x×]\s*[\d\s/\.]+"\s*[HWLD]?(?:\s*[x×]\s*[\d\s/\.]+"\s*[HWLD]?)?)',
        r'([\d.]+"\s*[HWLD]\s*[x×]\s*[\d.]+"\s*(?:Diameter|[HWLD]))',
        r'([\d.]+"\s*Diameter\s*[x×]\s*[\d.]+"\s*Diameter)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def main():
    if len(sys.argv) != 2:
        print("Usage: python scraper.py <url>", file=sys.stderr)
        sys.exit(1)
    
    url = sys.argv[1]
    if "viewpresentation.com" not in url:
        print("Error: URL must be from viewpresentation.com", file=sys.stderr)
        sys.exit(1)
    
    try:
        presentation = scrape(url)
        print(json.dumps(asdict(presentation), indent=2))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()