#!/usr/bin/env python3
"""
Zoho API Client for Item Master Management.

This module provides a client for interacting with the Zoho Books/Inventory API,
including OAuth2 authentication, Items API, Contacts API, and Custom Fields discovery.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from promo_parser.integrations.zoho.config import (
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

    def find_customer_by_account_number(self, account_number: str) -> Optional[Dict[str, Any]]:
        """
        Find a customer by their account number (contact_number field).

        Searches for contacts with contact_number matching the provided account number.
        Supports both raw account number (e.g., "10040") and prefixed format (e.g., "STBL-10040").

        Args:
            account_number: Account number to search for (with or without STBL- prefix)

        Returns:
            Customer contact if found, None otherwise
        """
        # Normalize: ensure STBL- prefix
        if not account_number.upper().startswith("STBL-"):
            search_term = f"STBL-{account_number}"
        else:
            search_term = account_number.upper()

        logger.debug(f"Searching for customer with account number: {search_term}")

        # Search contacts by the account number
        contacts = self.get_contacts(search_text=search_term, contact_type="customer")

        for contact in contacts:
            contact_number = contact.get("contact_number", "")
            if contact_number.upper() == search_term:
                logger.info(f"Found customer: {contact.get('contact_name')} (ID: {contact.get('contact_id')})")
                return contact

        # Also try without prefix in case it's stored differently
        raw_number = account_number.replace("STBL-", "").replace("stbl-", "")
        for contact in contacts:
            contact_number = contact.get("contact_number", "")
            if contact_number == raw_number:
                logger.info(f"Found customer by raw number: {contact.get('contact_name')} (ID: {contact.get('contact_id')})")
                return contact

        logger.warning(f"No customer found with account number: {search_term}")
        return None

    # =========================================================================
    # Estimates (Quotes) API
    # =========================================================================

    def create_estimate(self, estimate_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new estimate (quote) in Zoho Books.

        Estimates are created as draft by default and can be sent to customers
        or converted to sales orders/invoices.

        Args:
            estimate_data: Estimate payload including:
                - customer_id (required): Zoho customer ID
                - date: Estimate date (YYYY-MM-DD)
                - expiry_date: Quote expiry date
                - line_items: List of line item dicts
                - notes: Customer notes
                - terms: Terms and conditions
                - status: "draft" or "sent"

        Returns:
            Created estimate data including estimate_id, estimate_number
        """
        response = self._make_request("POST", "/estimates", json_data=estimate_data)
        return response.get("estimate", {})

    def get_estimate(self, estimate_id: str) -> Dict[str, Any]:
        """
        Get a single estimate by ID.

        Args:
            estimate_id: Zoho estimate ID

        Returns:
            Estimate data
        """
        response = self._make_request("GET", f"/estimates/{estimate_id}")
        return response.get("estimate", {})

    def get_estimates(
        self,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        search_text: Optional[str] = None,
        page: int = 1,
        per_page: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get estimates with optional filters.

        Args:
            customer_id: Filter by customer ID
            status: Filter by status (draft, sent, accepted, declined, invoiced)
            search_text: Search text
            page: Page number
            per_page: Estimates per page (max 200)

        Returns:
            List of estimates
        """
        params = {
            "page": page,
            "per_page": per_page
        }

        if customer_id:
            params["customer_id"] = customer_id
        if status:
            params["status"] = status
        if search_text:
            params["search_text"] = search_text

        response = self._make_request("GET", "/estimates", params=params)
        return response.get("estimates", [])

    def update_estimate(self, estimate_id: str, estimate_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing estimate.

        Args:
            estimate_id: Zoho estimate ID
            estimate_data: Updated estimate data

        Returns:
            Updated estimate data
        """
        response = self._make_request("PUT", f"/estimates/{estimate_id}", json_data=estimate_data)
        return response.get("estimate", {})

    def mark_estimate_as_sent(self, estimate_id: str) -> Dict[str, Any]:
        """
        Mark an estimate as sent.

        Use this when the estimate was sent to the customer through other means
        (not via Zoho's email).

        Args:
            estimate_id: Zoho estimate ID

        Returns:
            Response data
        """
        response = self._make_request("POST", f"/estimates/{estimate_id}/status/sent")
        return response

    def mark_estimate_as_accepted(self, estimate_id: str) -> Dict[str, Any]:
        """
        Mark an estimate as accepted.

        Use this when the customer has accepted the quote through other means.

        Args:
            estimate_id: Zoho estimate ID

        Returns:
            Response data
        """
        response = self._make_request("POST", f"/estimates/{estimate_id}/status/accepted")
        return response

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
        # Zoho returns customfields as a dict keyed by entity type
        all_custom_fields = response.get("customfields", {})
        custom_fields = all_custom_fields.get(entity, []) if isinstance(all_custom_fields, dict) else []
        
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

        # Track which Zoho field IDs have already been claimed to prevent collisions
        # This prevents "category" substring from matching "Promo Category" after
        # "promo category" already claimed it with an exact match
        claimed_field_ids = set()

        for field_name, label_patterns in patterns.items():
            field_map[field_name] = None

            # First pass: Look for EXACT matches (prevents "category" matching "promo category")
            for cf in custom_fields:
                if not isinstance(cf, dict):
                    continue
                cf_id = cf.get("customfield_id")
                # Skip if this Zoho field was already claimed by another pattern
                if cf_id in claimed_field_ids:
                    continue

                cf_label = cf.get("label", "").lower()
                cf_name = cf.get("field_name", "").lower()

                for pattern in label_patterns:
                    pattern_lower = pattern.lower()
                    # Exact match on label or field_name
                    if pattern_lower == cf_label or pattern_lower == cf_name:
                        field_map[field_name] = cf_id
                        claimed_field_ids.add(cf_id)
                        logger.debug(f"Exact matched '{field_name}' -> {cf.get('label')} (ID: {cf_id})")
                        break
                if field_map[field_name]:
                    break

            # Second pass: Fall back to substring match if no exact match
            if not field_map[field_name]:
                for cf in custom_fields:
                    if not isinstance(cf, dict):
                        logger.warning(f"Unexpected custom field format: {type(cf)}")
                        continue
                    cf_id = cf.get("customfield_id")
                    # Skip if this Zoho field was already claimed by another pattern
                    if cf_id in claimed_field_ids:
                        continue

                    cf_label = cf.get("label", "").lower()
                    cf_name = cf.get("field_name", "").lower()

                    for pattern in label_patterns:
                        pattern_lower = pattern.lower()
                        if pattern_lower in cf_label or pattern_lower in cf_name:
                            field_map[field_name] = cf_id
                            claimed_field_ids.add(cf_id)
                            logger.debug(f"Substring matched '{field_name}' -> {cf.get('label')} (ID: {cf_id})")
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

    # =========================================================================
    # Zoho WorkDrive API
    # =========================================================================

    WORKDRIVE_API_BASE = "https://www.zohoapis.com/workdrive/api/v1"
    _workdrive_access_token: Optional[str] = None
    _workdrive_token_expires_at: float = 0

    def _get_workdrive_access_token(self) -> str:
        """
        Get a valid access token for WorkDrive API.

        Uses the separate ZOHO_WORKDRIVE_REFRESH_TOKEN if available.
        """
        # Check if we have a cached valid token
        if self._workdrive_access_token and time.time() < self._workdrive_token_expires_at:
            return self._workdrive_access_token

        # Get WorkDrive-specific refresh token
        workdrive_refresh_token = os.getenv("ZOHO_WORKDRIVE_REFRESH_TOKEN")
        if not workdrive_refresh_token:
            # Fall back to main refresh token
            return self._get_access_token()

        # Exchange refresh token for access token
        response = requests.post(
            "https://accounts.zoho.com/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": workdrive_refresh_token
            }
        )

        if response.status_code != 200:
            raise ZohoAPIError(f"Failed to refresh WorkDrive token: {response.text}")

        data = response.json()
        self._workdrive_access_token = data.get("access_token")
        # Token expires in 1 hour, refresh 5 minutes early
        self._workdrive_token_expires_at = time.time() + data.get("expires_in", 3600) - 300

        return self._workdrive_access_token

    def _make_workdrive_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        files: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to Zoho WorkDrive API.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL or endpoint path
            params: Query parameters
            json_data: JSON body data
            files: Files to upload

        Returns:
            Response JSON

        Raises:
            ZohoAPIError: If the request fails
        """
        # Build full URL if not already complete
        if not url.startswith("http"):
            url = f"{self.WORKDRIVE_API_BASE}/{url.lstrip('/')}"

        headers = {
            "Authorization": f"Zoho-oauthtoken {self._get_workdrive_access_token()}"
        }

        # Only add Content-Type for JSON requests (not file uploads)
        if json_data and not files:
            headers["Content-Type"] = "application/json"

        logger.debug(f"WorkDrive API {method} {url}")

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

            if response.status_code >= 400:
                error_message = response_data.get("error", {}).get("message", response.text)
                raise ZohoAPIError(
                    f"WorkDrive API error: {error_message}",
                    status_code=response.status_code,
                    response=response_data
                )

            return response_data

        except requests.RequestException as e:
            raise ZohoAPIError(f"WorkDrive request failed: {e}")

    def get_workdrive_team_folders(self, team_id: str) -> List[Dict[str, Any]]:
        """
        Get all team folders in a team.

        Args:
            team_id: WorkDrive team ID

        Returns:
            List of team folder data
        """
        url = f"teams/{team_id}/teamfolders"
        response = self._make_workdrive_request("GET", url)
        return response.get("data", [])

    def search_workdrive_team_folders(self, folder_name: str, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for a team folder by name.

        Args:
            folder_name: Name to search for (partial match)
            team_id: WorkDrive team ID (defaults to ZOHO_WORKDRIVE_TEAM_ID env var)

        Returns:
            List of matching team folders
        """
        import os
        team_id = team_id or os.getenv("ZOHO_WORKDRIVE_TEAM_ID")
        if not team_id:
            raise ValueError("ZOHO_WORKDRIVE_TEAM_ID not set. Set it in .env or pass team_id parameter.")

        folders = self.get_workdrive_team_folders(team_id)

        # Filter by name (case-insensitive partial match)
        folder_name_lower = folder_name.lower()
        matching = []
        for folder in folders:
            attrs = folder.get("attributes", {})
            name = attrs.get("name", "")
            if folder_name_lower in name.lower():
                matching.append(folder)

        return matching

    def upload_file_to_workdrive(self, folder_id: str, file_path: str) -> Dict[str, Any]:
        """
        Upload a file to a WorkDrive folder.

        Args:
            folder_id: WorkDrive folder ID (parent_id)
            file_path: Local path to the file

        Returns:
            Uploaded file data including id and permalink
        """
        import os

        url = f"{self.WORKDRIVE_API_BASE}/upload"
        params = {
            "parent_id": folder_id,
            "override-name-exist": "true"  # Overwrite if file exists
        }

        filename = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            files = {"content": (filename, f)}
            response = self._make_workdrive_request("POST", url, params=params, files=files)

        # Response is {"data": [{"attributes": {...}}]} - extract first item
        data = response.get("data", [])
        if isinstance(data, list) and len(data) > 0:
            item = data[0]
            attrs = item.get("attributes", {})
            return {
                "id": attrs.get("resource_id"),
                "attributes": {
                    "permalink": attrs.get("Permalink"),
                    "name": attrs.get("FileName")
                }
            }
        return {}

    def upload_to_cost_calculators(self, file_path: str) -> Dict[str, Any]:
        """
        Upload a file to the 'Cost Calculators' team folder.

        This is a convenience method that uses the ZOHO_COST_CALCULATORS_FOLDER_ID
        environment variable.

        Args:
            file_path: Local path to the file

        Returns:
            Uploaded file data including id and permalink

        Raises:
            ValueError: If ZOHO_COST_CALCULATORS_FOLDER_ID is not set
        """
        import os

        folder_id = os.getenv("ZOHO_COST_CALCULATORS_FOLDER_ID")
        if not folder_id:
            raise ValueError(
                "ZOHO_COST_CALCULATORS_FOLDER_ID not set. "
                "Run 'python3 -c \"from zoho_client import ZohoClient; c = ZohoClient(); "
                "print(c.search_workdrive_team_folders('Cost Calculators'))\"' to find the folder ID."
            )

        return self.upload_file_to_workdrive(folder_id, file_path)


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
