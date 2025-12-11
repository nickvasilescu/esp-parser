#!/usr/bin/env python3
"""
Zoho API Client for Item Master Management.

This module provides a client for interacting with the Zoho Books/Inventory API,
including OAuth2 authentication, Items API, Contacts API, and Custom Fields discovery.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from zoho_config import (
    ZOHO_ORG_ID,
    ZOHO_CLIENT_ID,
    ZOHO_CLIENT_SECRET,
    ZOHO_REFRESH_TOKEN,
    ZOHO_API_BASE_URL,
    ZOHO_TOKEN_URL,
)

logger = logging.getLogger(__name__)


class ZohoAPIError(Exception):
    """Exception raised for Zoho API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class ZohoClient:
    """
    Client for Zoho Books/Inventory API.
    
    Handles OAuth2 authentication and provides methods for:
    - Items: GET, POST, PUT, upsert
    - Contacts: GET, search
    - Custom Fields: discovery
    - Image upload
    """
    
    def __init__(
        self,
        org_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        refresh_token: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize the Zoho client.
        
        Args:
            org_id: Zoho organization ID (defaults to env var)
            client_id: OAuth client ID (defaults to env var)
            client_secret: OAuth client secret (defaults to env var)
            refresh_token: OAuth refresh token (defaults to env var)
            base_url: API base URL (defaults to env var)
        """
        self.org_id = org_id or ZOHO_ORG_ID
        self.client_id = client_id or ZOHO_CLIENT_ID
        self.client_secret = client_secret or ZOHO_CLIENT_SECRET
        self.refresh_token = refresh_token or ZOHO_REFRESH_TOKEN
        self.base_url = base_url or ZOHO_API_BASE_URL
        
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        
        # Custom fields cache
        self._custom_fields_cache: Dict[str, List[Dict]] = {}
        
    # =========================================================================
    # Authentication
    # =========================================================================
    
    def _refresh_access_token(self) -> str:
        """
        Refresh the OAuth2 access token using the refresh token.
        
        Returns:
            New access token
            
        Raises:
            ZohoAPIError: If token refresh fails
        """
        logger.debug("Refreshing Zoho access token...")
        
        data = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token"
        }
        
        try:
            response = requests.post(ZOHO_TOKEN_URL, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            if "access_token" not in token_data:
                raise ZohoAPIError(
                    f"Token refresh failed: {token_data.get('error', 'Unknown error')}",
                    response=token_data
                )
            
            self._access_token = token_data["access_token"]
            # Token typically expires in 1 hour, refresh 5 minutes early
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = time.time() + expires_in - 300
            
            logger.debug("Access token refreshed successfully")
            return self._access_token
            
        except requests.RequestException as e:
            raise ZohoAPIError(f"Token refresh request failed: {e}")
    
    def _get_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Valid access token
        """
        if not self._access_token or time.time() >= self._token_expiry:
            return self._refresh_access_token()
        return self._access_token
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests including auth token."""
        return {
            "Authorization": f"Zoho-oauthtoken {self._get_access_token()}",
            "Content-Type": "application/json"
        }
    
    # =========================================================================
    # API Request Helpers
    # =========================================================================
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        files: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated API request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON body data
            files: Files to upload
            
        Returns:
            Response JSON
            
        Raises:
            ZohoAPIError: If the request fails
        """
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))
        
        # Always include organization_id in params
        if params is None:
            params = {}
        params["organization_id"] = self.org_id
        
        headers = self._get_headers()
        
        # Remove Content-Type header if uploading files
        if files:
            del headers["Content-Type"]
        
        logger.debug(f"Zoho API {method} {url}")
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                files=files
            )
            
            response_data = response.json() if response.content else {}
            
            # Check for Zoho API-level errors
            if response.status_code >= 400:
                error_message = response_data.get("message", response.text)
                raise ZohoAPIError(
                    f"API error: {error_message}",
                    status_code=response.status_code,
                    response=response_data
                )
            
            # Zoho returns code: 0 for success in response body
            code = response_data.get("code")
            if code is not None and code != 0:
                raise ZohoAPIError(
                    f"API error (code {code}): {response_data.get('message', 'Unknown error')}",
                    status_code=response.status_code,
                    response=response_data
                )
            
            return response_data
            
        except requests.RequestException as e:
            raise ZohoAPIError(f"Request failed: {e}")
    
    # =========================================================================
    # Items API
    # =========================================================================
    
    def get_items(
        self,
        search_text: Optional[str] = None,
        sku: Optional[str] = None,
        name: Optional[str] = None,
        filter_by: Optional[str] = None,
        page: int = 1,
        per_page: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get items from Zoho.
        
        Args:
            search_text: Search text to filter items
            sku: Filter by SKU
            name: Filter by item name
            filter_by: Filter status (Status.All, Status.Active, etc.)
            page: Page number
            per_page: Items per page (max 200)
            
        Returns:
            List of items
        """
        params = {
            "page": page,
            "per_page": per_page
        }
        
        if search_text:
            params["search_text"] = search_text
        if sku:
            params["sku"] = sku
        if name:
            params["name"] = name
        if filter_by:
            params["filter_by"] = filter_by
        
        response = self._make_request("GET", "/items", params=params)
        return response.get("items", [])
    
    def get_item_by_id(self, item_id: str) -> Dict[str, Any]:
        """
        Get a single item by ID.
        
        Args:
            item_id: Zoho item ID
            
        Returns:
            Item data
        """
        response = self._make_request("GET", f"/items/{item_id}")
        return response.get("item", {})
    
    def get_item_by_sku(self, sku: str, item_name: str = None, part_number: str = None) -> Optional[Dict[str, Any]]:
        """
        Get an item by SKU with STRICT matching.
        
        Only returns an item if it's a true match - avoids overwriting
        different products that share partial SKU components.
        
        Matching priority:
        1. Exact SKU match
        2. Exact name match (since name = SKU in new format)
        3. Old STBL- format match (for migration only)
        
        Args:
            sku: Item SKU (new format)
            item_name: Optional item name for fallback search
            part_number: Optional part number (MPN) for fallback search
            
        Returns:
            Item data or None if not found
        """
        # Try exact SKU match first
        items = self.get_items(sku=sku)
        if items:
            for item in items:
                if item.get("sku") == sku:
                    return item
        
        # Try exact name match (since name = SKU in new format)
        if item_name:
            items = self.get_items(name=item_name)
            if items:
                for item in items:
                    if item.get("name") == item_name:
                        logger.info(f"Found item by exact name match: {item_name}")
                        return item
        
        # Try with "STBL-" prefix (old SAGE format migration only)
        # Extract base SKU components: <client>-<baseCode> without variations
        sku_parts = sku.split("-")
        if len(sku_parts) >= 2:
            client_id = sku_parts[0]
            base_code = sku_parts[1]
            old_format_sku = f"STBL-{client_id}-{base_code}"
            
            items = self.get_items(search_text=old_format_sku)
            if items:
                for item in items:
                    item_sku = item.get("sku", "")
                    # Must match client + base code exactly
                    if item_sku.startswith(old_format_sku):
                        logger.info(f"Found item with old STBL- format: {item_sku} -> will update to {sku}")
                        return item
        
        # NOTE: Removed loose fallback searches that were causing overwrites!
        # The old logic matched ANY item ending with the same color/variation,
        # which caused different products to overwrite each other.
        # 
        # If we reach here, we should CREATE a new item, not find a wrong match.
        
        return None
    
    def create_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new item.
        
        Args:
            item_data: Item data dictionary
            
        Returns:
            Created item data
        """
        response = self._make_request("POST", "/items", json_data=item_data)
        return response.get("item", {})
    
    def update_item(self, item_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing item.
        
        Args:
            item_id: Zoho item ID
            item_data: Updated item data
            
        Returns:
            Updated item data
        """
        response = self._make_request("PUT", f"/items/{item_id}", json_data=item_data)
        return response.get("item", {})
    
    def upsert_item(self, item_data: Dict[str, Any], unique_field: str = "sku") -> Dict[str, Any]:
        """
        Create or update an item based on a unique field.
        
        Args:
            item_data: Item data dictionary (must include the unique field)
            unique_field: Field to use for matching (default: sku)
            
        Returns:
            Created or updated item data
        """
        unique_value = item_data.get(unique_field)
        if not unique_value:
            raise ValueError(f"Item data must include '{unique_field}' for upsert")
        
        # Try to find existing item
        existing_item = None
        if unique_field == "sku":
            # Pass additional fields for fallback searches (handles SKU migrations)
            existing_item = self.get_item_by_sku(
                unique_value,
                item_name=item_data.get("name"),
                part_number=item_data.get("part_number")
            )
        else:
            # For custom fields, search by the field value
            items = self.get_items(search_text=unique_value)
            for item in items:
                # Check custom fields
                for cf in item.get("custom_fields", []):
                    if cf.get("value") == unique_value:
                        existing_item = item
                        break
        
        if existing_item:
            logger.info(f"Updating existing item (ID: {existing_item['item_id']}) with {unique_field}={unique_value}")
            return self.update_item(existing_item["item_id"], item_data)
        else:
            logger.info(f"Creating new item with {unique_field}={unique_value}")
            return self.create_item(item_data)
    
    def upload_item_image(self, item_id: str, image_path: str) -> Dict[str, Any]:
        """
        Upload an image for an item.
        
        Args:
            item_id: Zoho item ID
            image_path: Path to image file
            
        Returns:
            Response data
        """
        with open(image_path, "rb") as f:
            files = {"image": f}
            response = self._make_request("POST", f"/items/{item_id}/image", files=files)
        return response
    
    def upload_item_image_from_url(self, item_id: str, image_url: str) -> Dict[str, Any]:
        """
        Upload an image for an item from a URL.
        
        Downloads the image and uploads it to Zoho.
        
        Args:
            item_id: Zoho item ID
            image_url: URL of the image
            
        Returns:
            Response data
        """
        # Download image
        logger.debug(f"Downloading image from {image_url}")
        image_response = requests.get(image_url, stream=True)
        image_response.raise_for_status()
        
        # Determine filename from URL or content-disposition
        content_disposition = image_response.headers.get("content-disposition", "")
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[1].strip('"')
        else:
            filename = image_url.split("/")[-1].split("?")[0] or "image.jpg"
        
        # Upload to Zoho
        files = {"image": (filename, image_response.content)}
        response = self._make_request("POST", f"/items/{item_id}/image", files=files)
        return response
    
    # =========================================================================
    # Contacts API
    # =========================================================================
    
    def get_contacts(
        self,
        search_text: Optional[str] = None,
        contact_type: Optional[str] = None,
        filter_by: Optional[str] = None,
        page: int = 1,
        per_page: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get contacts from Zoho.
        
        Args:
            search_text: Search text (searches name, company, email)
            contact_type: Filter by type (customer, vendor)
            filter_by: Filter status
            page: Page number
            per_page: Contacts per page
            
        Returns:
            List of contacts
        """
        params = {
            "page": page,
            "per_page": per_page
        }
        
        if search_text:
            params["search_text"] = search_text
        if contact_type:
            params["contact_type"] = contact_type
        if filter_by:
            params["filter_by"] = filter_by
        
        response = self._make_request("GET", "/contacts", params=params)
        return response.get("contacts", [])
    
    def search_contacts(
        self,
        name: Optional[str] = None,
        email: Optional[str] = None,
        company_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search contacts by name, email, or company.
        
        Args:
            name: Contact name to search
            email: Email to search
            company_name: Company name to search
            
        Returns:
            List of matching contacts
        """
        search_terms = []
        if name:
            search_terms.append(name)
        if email:
            search_terms.append(email)
        if company_name:
            search_terms.append(company_name)
        
        if not search_terms:
            return []
        
        # Try each search term and combine results
        all_contacts = []
        seen_ids = set()
        
        for term in search_terms:
            contacts = self.get_contacts(search_text=term)
            for contact in contacts:
                contact_id = contact.get("contact_id")
                if contact_id and contact_id not in seen_ids:
                    all_contacts.append(contact)
                    seen_ids.add(contact_id)
        
        return all_contacts
    
    def get_contact_by_id(self, contact_id: str) -> Dict[str, Any]:
        """
        Get a single contact by ID.
        
        Args:
            contact_id: Zoho contact ID
            
        Returns:
            Contact data
        """
        response = self._make_request("GET", f"/contacts/{contact_id}")
        return response.get("contact", {})
    
    # =========================================================================
    # Custom Fields API
    # =========================================================================
    
    def get_custom_fields(self, entity: str = "item", force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get custom fields for an entity type.
        
        Args:
            entity: Entity type (item, contact, etc.)
            force_refresh: Force refresh of cache
            
        Returns:
            List of custom fields
        """
        # Check cache first
        if not force_refresh and entity in self._custom_fields_cache:
            return self._custom_fields_cache[entity]
        
        response = self._make_request("GET", f"/settings/customfields", params={"entity": entity})
        custom_fields = response.get("customfields", [])
        
        # Cache the result
        self._custom_fields_cache[entity] = custom_fields
        
        return custom_fields
    
    def discover_custom_fields(
        self,
        patterns: Dict[str, List[str]],
        entity: str = "item"
    ) -> Dict[str, Optional[str]]:
        """
        Discover custom fields by pattern matching labels.
        
        This is the "fail-safe" mechanism - only returns field IDs for
        fields that actually exist in Zoho and match the patterns.
        
        Args:
            patterns: Dict mapping field names to list of label patterns
            entity: Entity type to search
            
        Returns:
            Dict mapping field names to custom field IDs (None if not found)
        """
        custom_fields = self.get_custom_fields(entity=entity)
        
        field_map: Dict[str, Optional[str]] = {}
        
        for field_name, label_patterns in patterns.items():
            field_map[field_name] = None
            
            for cf in custom_fields:
                cf_label = cf.get("label", "").lower()
                cf_name = cf.get("field_name", "").lower()
                
                for pattern in label_patterns:
                    pattern_lower = pattern.lower()
                    if pattern_lower in cf_label or pattern_lower in cf_name:
                        field_map[field_name] = cf.get("customfield_id")
                        logger.debug(f"Matched custom field '{field_name}' -> {cf.get('label')} (ID: {cf.get('customfield_id')})")
                        break
                
                if field_map[field_name]:
                    break
            
            if not field_map[field_name]:
                logger.debug(f"No match found for custom field '{field_name}'")
        
        return field_map
    
    # =========================================================================
    # Categories API (optional)
    # =========================================================================
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """
        Get item categories.
        
        Returns:
            List of categories
        """
        response = self._make_request("GET", "/items/categories")
        return response.get("categories", [])
    
    def find_category(self, category_name: str) -> Optional[str]:
        """
        Find a category by name.
        
        Args:
            category_name: Category name to search for
            
        Returns:
            Category ID if found, None otherwise
        """
        categories = self.get_categories()
        
        category_name_lower = category_name.lower()
        for cat in categories:
            if cat.get("name", "").lower() == category_name_lower:
                return cat.get("category_id")
        
        return None
    
    # =========================================================================
    # Vendors API (placeholder - deferred feature)
    # =========================================================================
    
    def get_vendors(self, search_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get vendors (contacts with vendor type).
        
        Args:
            search_text: Search text
            
        Returns:
            List of vendor contacts
        """
        return self.get_contacts(search_text=search_text, contact_type="vendor")
    
    def find_vendor_by_website(self, website_url: str) -> Optional[Dict[str, Any]]:
        """
        Find a vendor by website URL.
        
        This is the primary vendor matching mechanism per Koell's requirements.
        
        Args:
            website_url: Vendor website URL
            
        Returns:
            Vendor contact if found, None otherwise
        """
        # Normalize URL for comparison
        website_lower = website_url.lower().replace("https://", "").replace("http://", "").rstrip("/")
        
        vendors = self.get_vendors()
        
        for vendor in vendors:
            vendor_website = vendor.get("website", "")
            if vendor_website:
                vendor_website_lower = vendor_website.lower().replace("https://", "").replace("http://", "").rstrip("/")
                if vendor_website_lower == website_lower:
                    return vendor
        
        return None


# =============================================================================
# Module-level helper functions (for agent tool use)
# =============================================================================

def create_zoho_client() -> ZohoClient:
    """Create a ZohoClient instance with configuration from environment."""
    return ZohoClient()


if __name__ == "__main__":
    # Test the client
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        from zoho_config import validate_zoho_config
        validate_zoho_config()
        
        client = create_zoho_client()
        
        # Test authentication
        print("Testing Zoho API authentication...")
        token = client._get_access_token()
        print(f"Access token obtained: {token[:20]}...")
        
        # Test getting items
        print("\nFetching items...")
        items = client.get_items(per_page=5)
        print(f"Found {len(items)} items")
        
        # Test getting custom fields
        print("\nFetching item custom fields...")
        custom_fields = client.get_custom_fields(entity="item")
        print(f"Found {len(custom_fields)} custom fields:")
        for cf in custom_fields:
            print(f"  - {cf.get('label')} (ID: {cf.get('customfield_id')})")
        
        # Test getting contacts
        print("\nFetching contacts...")
        contacts = client.get_contacts(per_page=5)
        print(f"Found {len(contacts)} contacts")
        
        print("\nZoho client test completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
