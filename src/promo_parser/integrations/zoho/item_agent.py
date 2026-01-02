#!/usr/bin/env python3
"""
Zoho Item Master LLM Agent.

This module implements a Claude Opus 4.5 agent with extended thinking
that processes unified ESP/SAGE output and uploads to Zoho Item Master.

The agent:
1. Searches Zoho Contacts to get Client Account Number
2. Discovers existing custom fields via pattern matching
3. Transforms data according to business rules
4. Upserts items to Zoho Item Master
5. Uploads images if available

Usage:
    from zoho_item_agent import ZohoItemMasterAgent
    
    agent = ZohoItemMasterAgent()
    result = agent.process_unified_output(unified_output)
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

from anthropic import Anthropic

from promo_parser.integrations.zoho.config import (
    ZOHO_AGENT_MODEL,
    ZOHO_AGENT_THINKING_BUDGET,
    ZOHO_AGENT_MAX_TOKENS,
    ZOHO_AGENT_MAX_ITERATIONS,
    CUSTOM_FIELD_PATTERNS,
    validate_zoho_config,
    get_zoho_config_summary,
)
from promo_parser.integrations.zoho.client import ZohoClient, ZohoAPIError, create_zoho_client

# Import JobStateManager for state updates (optional dependency)
try:
    from promo_parser.core.state import JobStateManager, WorkflowStatus
except ImportError:
    JobStateManager = None
    WorkflowStatus = None
from promo_parser.integrations.zoho.transformer import (
    build_item_name_sku,
    get_base_code,
    get_vendor_sku,
    get_mpn,
    extract_base_pricing,
    extract_all_price_tiers,
    map_custom_fields,
    build_item_payload,
    validate_item_payload,
    explode_product_variations,
    build_fee_items,
    prepare_products_for_zoho,
    extract_numeric_account,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Result Types
# =============================================================================

@dataclass
class ItemUploadResult:
    """Result of a single item upload."""
    success: bool
    zoho_sku: str
    item_id: Optional[str] = None
    action: str = ""  # "created" or "updated"
    error: Optional[str] = None
    image_uploaded: bool = False


@dataclass
class AgentResult:
    """Overall result of the agent processing."""
    success: bool
    total_products: int = 0
    successful_uploads: int = 0
    failed_uploads: int = 0
    items: List[ItemUploadResult] = field(default_factory=list)
    client_account_number: Optional[str] = None
    discovered_custom_fields: Dict[str, Optional[str]] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0


# =============================================================================
# Tool Definitions for Claude
# =============================================================================

AGENT_TOOLS = [
    {
        "name": "search_zoho_contact",
        "description": "Search for a contact in Zoho by name, email, or company. Returns the contact's account number which is needed for building item SKUs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Contact name to search for"
                },
                "email": {
                    "type": "string",
                    "description": "Email address to search for"
                },
                "company_name": {
                    "type": "string",
                    "description": "Company name to search for"
                }
            }
        }
    },
    {
        "name": "discover_custom_fields",
        "description": "Discover which custom fields exist in Zoho Item Master. Returns a mapping of field names to their Zoho IDs. Only fields that exist will be populated during upload.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "upsert_item",
        "description": "Create or update items in Zoho Item Master with FULL variation and fee expansion. This creates SEPARATE Zoho items for: (1) Each product variation (color, size, decoration method), (2) Each fee (setup, rush, additional charges). Returns count of items and fees created.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_index": {
                    "type": "integer",
                    "description": "Index of the product in the unified output to upload"
                },
                "client_account_number": {
                    "type": "string",
                    "description": "Client account number for SKU construction"
                },
                "include_variations": {
                    "type": "boolean",
                    "description": "Create separate items for each color/size/decoration variation. Default: false (Koell wants base item only).",
                    "default": False
                },
                "include_fees": {
                    "type": "boolean",
                    "description": "Create separate items for fees (setup, rush, etc). Default: false",
                    "default": False
                }
            },
            "required": ["product_index", "client_account_number"]
        }
    },
    {
        "name": "upload_item_image",
        "description": "Upload an image to an existing Zoho item from a URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "Zoho item ID"
                },
                "image_url": {
                    "type": "string",
                    "description": "URL of the image to upload"
                }
            },
            "required": ["item_id", "image_url"]
        }
    },
    {
        "name": "get_categories",
        "description": "Get available item categories from Zoho to map product categories.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "create_item_pricebooks",
        "description": "Create sales and purchase pricebooks for an item with quantity-based tiered pricing. Call this AFTER upserting the item to set up tiered pricing for quotes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "Zoho item ID returned from upsert_item"
                },
                "item_sku": {
                    "type": "string",
                    "description": "Item SKU (name) for pricebook naming"
                },
                "client_account": {
                    "type": "string",
                    "description": "Client account number for pricebook naming"
                },
                "sales_tiers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "quantity": {"type": "integer"},
                            "rate": {"type": "number"}
                        }
                    },
                    "description": "Sales price tiers from presentation (qty/rate pairs)"
                },
                "purchase_tiers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "quantity": {"type": "integer"},
                            "rate": {"type": "number"}
                        }
                    },
                    "description": "Purchase cost tiers from distributor report (qty/rate pairs)"
                }
            },
            "required": ["item_id", "item_sku", "client_account"]
        }
    },
    {
        "name": "report_completion",
        "description": "Report that all items have been processed and the agent task is complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of what was accomplished"
                },
                "successful_count": {
                    "type": "integer",
                    "description": "Number of items successfully uploaded"
                },
                "failed_count": {
                    "type": "integer",
                    "description": "Number of items that failed"
                }
            },
            "required": ["summary", "successful_count", "failed_count"]
        }
    }
]


# =============================================================================
# Agent System Prompt
# =============================================================================

AGENT_SYSTEM_PROMPT = """You are a Zoho Item Master Management Agent. Your task is to process unified product data from ESP or SAGE presentations and upload items to Zoho.

## Your Workflow

1. **First**: Search for the client contact in Zoho to get their account number. Use the client information from the unified output (client name, email, company).

2. **Second**: Discover which custom fields exist in Zoho Item Master. This ensures we only populate fields that actually exist (fail-safe approach).

3. **Third**: Optionally get Zoho categories to map product categories.

4. **Fourth**: For each product in the unified output:
   - Call upsert_item with the product index and client account number
   - The system automatically expands products into variations (color/size/decoration method)
   - Each variation becomes a separate item with name/SKU format: <clientAccountId>-<baseCode>-<color>-<size>-<decoMethod>
   - Fee items are also created as separate products
   - After item upsert, call create_item_pricebooks to set up quantity-based tiered pricing
   - If the product has images and upload succeeds, call upload_item_image

5. **Finally**: Call report_completion with a summary of the results.

## Key Business Rules

- **Name = SKU**: Both name and SKU use the same format: <clientAccountId>-<baseCode>-<color>-<size>-<decoMethod>
  - Example: "10041-996M-BLKHEATHER-4X-EMBOSSED"
- **Variations**: Each color/size/decoration combo becomes a separate item
- **Fees**: Setup charges, additional color fees, etc. become separate fee items
- **MPN (part_number)**: Set to vendor's actual item number for Purchase Orders
- **Tiered Pricing**: After item creation, call create_item_pricebooks with price tiers from the data
  - Sales tiers from presentation sell_price breaks
  - Purchase tiers from distributor net_cost breaks
- **Inventory**: Always disabled (track_inventory = false)
- **Custom Fields**: Only populate fields that were discovered to exist
- **Images**: Upload primary image if available (SAGE products typically have images)

## Error Handling

- If client contact is not found, use "UNKNOWN" as account number and continue
- If custom field discovery fails, continue without custom fields
- If individual item upload fails, log the error and continue with other items
- If pricebook creation fails, log error but item creation still counts as success
- If image upload fails, log but don't fail the entire item

## Important Notes

- Process ALL products, don't stop early
- Always call report_completion when done, even if some items failed
- Be thorough but efficient - minimize unnecessary API calls
"""


# =============================================================================
# Agent Implementation
# =============================================================================

class ZohoItemMasterAgent:
    """
    Claude Opus 4.5 agent for Zoho Item Master management.
    
    Uses extended thinking for complex decision making and
    tool use for Zoho API interactions.
    """
    
    def __init__(
        self,
        zoho_client: Optional[ZohoClient] = None,
        anthropic_client: Optional[Anthropic] = None,
        model: str = ZOHO_AGENT_MODEL,
        thinking_budget: int = ZOHO_AGENT_THINKING_BUDGET,
        max_tokens: int = ZOHO_AGENT_MAX_TOKENS,
        max_iterations: int = ZOHO_AGENT_MAX_ITERATIONS,
        state_manager: Optional["JobStateManager"] = None,
        client_email: Optional[str] = None
    ):
        """
        Initialize the agent.

        Args:
            zoho_client: ZohoClient instance (created if not provided)
            anthropic_client: Anthropic client (created if not provided)
            model: Claude model ID
            thinking_budget: Token budget for extended thinking
            max_tokens: Max tokens for responses
            max_iterations: Max tool use iterations
            state_manager: Optional JobStateManager for state updates
            client_email: Optional client email for Zoho contact lookup
        """
        self.zoho_client = zoho_client or create_zoho_client()
        self.anthropic = anthropic_client or Anthropic()
        self.model = model
        self.thinking_budget = thinking_budget
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.state_manager = state_manager
        self.client_email = client_email

        # State for current processing session
        self._unified_output: Optional[Dict[str, Any]] = None
        self._discovered_fields: Dict[str, Optional[str]] = {}
        self._category_map: Dict[str, str] = {}
        self._results: List[ItemUploadResult] = []
        self._agent_complete = False
        self._items_uploaded = 0
        self._total_items = 0

    def _update_state(self, status: str, **kwargs) -> None:
        """Update job state if state manager is available."""
        if self.state_manager and WorkflowStatus:
            self.state_manager.update(status, **kwargs)
        
    def _handle_tool_call(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Handle a tool call from Claude.
        
        Args:
            tool_name: Name of the tool to call
            tool_input: Input parameters for the tool
            
        Returns:
            Tool result as string (will be sent back to Claude)
        """
        logger.info(f"Tool call: {tool_name}")
        logger.debug(f"Tool input: {json.dumps(tool_input, indent=2)}")
        
        try:
            if tool_name == "search_zoho_contact":
                return self._tool_search_contact(tool_input)
            
            elif tool_name == "discover_custom_fields":
                return self._tool_discover_custom_fields()
            
            elif tool_name == "upsert_item":
                return self._tool_upsert_item(tool_input)
            
            elif tool_name == "upload_item_image":
                return self._tool_upload_image(tool_input)
            
            elif tool_name == "get_categories":
                return self._tool_get_categories()
            
            elif tool_name == "create_item_pricebooks":
                return self._tool_create_item_pricebooks(tool_input)
            
            elif tool_name == "report_completion":
                return self._tool_report_completion(tool_input)
            
            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
                
        except Exception as e:
            logger.error(f"Tool error ({tool_name}): {e}")
            return json.dumps({"error": str(e)})
    
    def _tool_search_contact(self, tool_input: Dict[str, Any]) -> str:
        """Search for a Zoho contact."""
        self._update_state(
            WorkflowStatus.ZOHO_SEARCHING_CUSTOMER.value if WorkflowStatus else "zoho_searching_customer"
        )

        # Emit thought for customer search
        if self.state_manager:
            search_term = tool_input.get("name") or tool_input.get("email") or tool_input.get("company_name") or "unknown"
            self.state_manager.emit_thought(
                agent="zoho_item_agent",
                event_type="action",
                content=f"Searching Zoho for customer: {search_term}"
            )

        contacts = self.zoho_client.search_contacts(
            name=tool_input.get("name"),
            email=tool_input.get("email"),
            company_name=tool_input.get("company_name")
        )

        if contacts:
            contact = contacts[0]
            # Emit success thought
            if self.state_manager:
                self.state_manager.emit_thought(
                    agent="zoho_item_agent",
                    event_type="success",
                    content=f"Found customer: {contact.get('contact_name')} ({contact.get('contact_number')})"
                )
            return json.dumps({
                "found": True,
                "contact_id": contact.get("contact_id"),
                "contact_number": contact.get("contact_number"),
                "contact_name": contact.get("contact_name"),
                "company_name": contact.get("company_name"),
                "email": contact.get("email")
            })
        else:
            # Emit not found thought
            if self.state_manager:
                self.state_manager.emit_thought(
                    agent="zoho_item_agent",
                    event_type="observation",
                    content="Customer not found in Zoho, using UNKNOWN"
                )
            return json.dumps({
                "found": False,
                "message": "No matching contact found. You may use 'UNKNOWN' as the account number."
            })
    
    def _tool_discover_custom_fields(self) -> str:
        """Discover custom fields in Zoho."""
        self._update_state(
            WorkflowStatus.ZOHO_DISCOVERING_FIELDS.value if WorkflowStatus else "zoho_discovering_fields"
        )
        try:
            self._discovered_fields = self.zoho_client.discover_custom_fields(
                patterns=CUSTOM_FIELD_PATTERNS,
                entity="item"
            )
            
            # Count discovered vs not found
            discovered = {k: v for k, v in self._discovered_fields.items() if v is not None}
            not_found = [k for k, v in self._discovered_fields.items() if v is None]
            
            return json.dumps({
                "success": True,
                "discovered_count": len(discovered),
                "not_found_count": len(not_found),
                "discovered_fields": list(discovered.keys()),
                "not_found_fields": not_found,
                "message": f"Discovered {len(discovered)} custom fields. {len(not_found)} patterns did not match any existing fields."
            })
        except ZohoAPIError as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Custom field discovery failed. Continuing without custom fields."
            })
    
    def _tool_upsert_item(self, tool_input: Dict[str, Any]) -> str:
        """
        Upsert an item to Zoho with full variation and fee expansion.

        Creates separate Zoho items for:
        1. Each product variation (color, size, decoration method)
        2. Each fee associated with the product
        """
        product_index = tool_input.get("product_index")
        client_account_number = tool_input.get("client_account_number")
        include_variations = tool_input.get("include_variations", False)
        include_fees = tool_input.get("include_fees", True)

        if self._unified_output is None:
            return json.dumps({"error": "No unified output loaded"})

        products = self._unified_output.get("products", [])
        if product_index < 0 or product_index >= len(products):
            return json.dumps({"error": f"Invalid product index: {product_index}"})

        product = products[product_index]
        product_name = product.get("item", {}).get("name", "Unknown")

        # Emit per-item progress
        self._items_uploaded += 1
        self._update_state(
            WorkflowStatus.ZOHO_UPLOADING_ITEMS.value if WorkflowStatus else "zoho_uploading_items",
            current_item=self._items_uploaded,
            total_items=self._total_items,
            current_item_name=product_name
        )

        # Emit thought for item upsert
        if self.state_manager:
            self.state_manager.emit_thought(
                agent="zoho_item_agent",
                event_type="action",
                content=f"Upserting item to Zoho: {product_name}",
                metadata={"product_index": product_index, "item_number": self._items_uploaded, "total_items": self._total_items}
            )
        
        try:
            # Get base code for naming
            base_code = get_base_code(product)
            if not base_code:
                result = ItemUploadResult(
                    success=False,
                    zoho_sku="",
                    error="No base code found in product data"
                )
                self._results.append(result)
                return json.dumps({"success": False, "error": result.error})
            
            # Find category if available
            category_id = None
            item_categories = product.get("item", {}).get("categories", [])
            for cat in item_categories:
                if cat in self._category_map:
                    category_id = self._category_map[cat]
                    break
            
            # === STEP 1: Explode variations (disabled by default) ===
            if include_variations:
                variations = explode_product_variations(product)
            else:
                variations = [{}]  # Single base item (Koell: avoid variant explosion)
            
            logger.info(f"Product '{product_name}': {len(variations)} variation(s)")
            
            # === STEP 2: Create items for each variation ===
            # Get presentation URL from metadata for custom fields
            presentation_url = self._unified_output.get("metadata", {}).get("presentation_url")

            created_items = []
            for variation in variations:
                payload = build_item_payload(
                    product=product,
                    client_account_number=client_account_number,
                    discovered_fields=self._discovered_fields,
                    variation=variation if variation else None,
                    category_id=category_id,
                    presentation_url=presentation_url
                )
                
                # Extract and remove metadata
                price_tiers = payload.pop("_price_tiers", {"sales_tiers": [], "purchase_tiers": []})
                payload.pop("_variation", None)
                original_name = payload.pop("_original_name", "")
                payload.pop("_is_variation", None)
                payload.pop("_fee_type", None)
                payload.pop("_source_product", None)
                payload.pop("_parsed_from", None)
                payload.pop("_source_identifiers", None)
                payload.pop("_source", None)
                payload.pop("_percent", None)
                
                zoho_sku = payload.get("sku", "")
                
                # Validate
                errors = validate_item_payload(payload)
                if errors:
                    logger.warning(f"Validation failed for {zoho_sku}: {errors}")
                    continue
                
                # Upsert to Zoho
                zoho_item = self.zoho_client.upsert_item(payload)
                
                result = ItemUploadResult(
                    success=True,
                    zoho_sku=zoho_sku,
                    item_id=zoho_item.get("item_id"),
                    action="created"
                )
                self._results.append(result)
                
                created_items.append({
                    "item_id": zoho_item.get("item_id"),
                    "sku": zoho_sku,
                    "variation": variation,
                    "type": "product"
                })
            
            # === STEP 3: Create fee items ===
            fee_items_created = []
            if include_fees:
                fee_payloads = build_fee_items(
                    product=product,
                    client_account_number=client_account_number,
                    discovered_fields=self._discovered_fields
                )
                
                logger.info(f"Product '{product_name}': {len(fee_payloads)} fee item(s)")
                
                for fee_payload in fee_payloads:
                    # Extract and remove metadata
                    fee_type = fee_payload.pop("_fee_type", None)
                    fee_payload.pop("_source_product", None)
                    fee_payload.pop("_parsed_from", None)
                    fee_payload.pop("_percent", None)
                    
                    fee_sku = fee_payload.get("sku", "")
                    
                    # Validate
                    errors = validate_item_payload(fee_payload)
                    if errors:
                        logger.warning(f"Fee validation failed for {fee_sku}: {errors}")
                        continue
                    
                    # Upsert fee to Zoho
                    try:
                        zoho_fee_item = self.zoho_client.upsert_item(fee_payload)
                        
                        fee_result = ItemUploadResult(
                            success=True,
                            zoho_sku=fee_sku,
                            item_id=zoho_fee_item.get("item_id"),
                            action="created"
                        )
                        self._results.append(fee_result)
                        
                        fee_items_created.append({
                            "item_id": zoho_fee_item.get("item_id"),
                            "sku": fee_sku,
                            "fee_type": fee_type,
                            "type": "fee"
                        })
                    except Exception as e:
                        logger.error(f"Failed to create fee item {fee_sku}: {e}")
            
            # Emit success thought
            if self.state_manager:
                self.state_manager.emit_thought(
                    agent="zoho_item_agent",
                    event_type="success",
                    content=f"Created {len(created_items)} item(s) for: {product_name}",
                    metadata={"variations": len(created_items), "fees": len(fee_items_created)}
                )

            return json.dumps({
                "success": True,
                "product_name": product_name,
                "base_code": base_code,
                "client_account": client_account_number,
                "variations_created": len(created_items),
                "fees_created": len(fee_items_created),
                "items": created_items,
                "fee_items": fee_items_created,
                "has_images": len(product.get("images", [])) > 0,
                "summary": f"Created {len(created_items)} product variation(s) + {len(fee_items_created)} fee item(s)"
            })
            
        except ZohoAPIError as e:
            result = ItemUploadResult(
                success=False,
                zoho_sku=zoho_sku if 'zoho_sku' in locals() else "",
                error=str(e)
            )
            self._results.append(result)
            return json.dumps({"success": False, "error": str(e)})
    
    def _tool_upload_image(self, tool_input: Dict[str, Any]) -> str:
        """Upload an image to a Zoho item."""
        item_id = tool_input.get("item_id")
        image_url = tool_input.get("image_url")
        
        try:
            self.zoho_client.upload_item_image_from_url(item_id, image_url)
            
            # Update result to mark image uploaded
            for result in self._results:
                if result.item_id == item_id:
                    result.image_uploaded = True
                    break
            
            return json.dumps({
                "success": True,
                "message": f"Image uploaded successfully for item {item_id}"
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Image upload failed but item was created/updated successfully"
            })
    
    def _tool_get_categories(self) -> str:
        """Get Zoho item categories."""
        try:
            categories = self.zoho_client.get_categories()
            
            # Build category map
            self._category_map = {cat.get("name"): cat.get("category_id") for cat in categories}
            
            return json.dumps({
                "success": True,
                "category_count": len(categories),
                "categories": [{"name": cat.get("name"), "id": cat.get("category_id")} for cat in categories]
            })
            
        except ZohoAPIError as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Could not fetch categories. Products will be uploaded without category."
            })
    
    def _tool_create_item_pricebooks(self, tool_input: Dict[str, Any]) -> str:
        """Create sales and purchase pricebooks for an item with tiered pricing."""
        item_id = tool_input.get("item_id")
        item_sku = tool_input.get("item_sku")
        client_account = tool_input.get("client_account")
        sales_tiers = tool_input.get("sales_tiers", [])
        purchase_tiers = tool_input.get("purchase_tiers", [])
        
        if not item_id or not item_sku or not client_account:
            return json.dumps({
                "success": False,
                "error": "item_id, item_sku, and client_account are required"
            })
        
        try:
            result = self.zoho_client.create_item_pricebooks(
                item_id=item_id,
                item_sku=item_sku,
                client_account=client_account,
                sales_tiers=sales_tiers,
                purchase_tiers=purchase_tiers
            )
            
            return json.dumps({
                "success": True,
                "sales_pricebook": result.get("sales_pricebook", {}).get("name") if result.get("sales_pricebook") else None,
                "purchase_pricebook": result.get("purchase_pricebook", {}).get("name") if result.get("purchase_pricebook") else None,
                "errors": result.get("errors", []),
                "message": "Pricebooks created/updated successfully" if not result.get("errors") else f"Pricebooks created with {len(result.get('errors', []))} error(s)"
            })
            
        except ZohoAPIError as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to create pricebooks"
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Unexpected error creating pricebooks"
            })
    
    def _tool_report_completion(self, tool_input: Dict[str, Any]) -> str:
        """Mark agent as complete."""
        self._agent_complete = True

        summary = tool_input.get("summary", "Processing complete")
        successful = tool_input.get("successful_count", 0)
        failed = tool_input.get("failed_count", 0)

        # Emit completion thought
        if self.state_manager:
            self.state_manager.emit_thought(
                agent="zoho_item_agent",
                event_type="checkpoint",
                content=f"Item Master upload complete: {successful} successful, {failed} failed",
                metadata={"successful": successful, "failed": failed}
            )

        return json.dumps({
            "acknowledged": True,
            "summary": summary,
            "successful": successful,
            "failed": failed
        })
    
    def process_unified_output(
        self,
        unified_output: Dict[str, Any],
        dry_run: bool = False
    ) -> AgentResult:
        """
        Process unified ESP/SAGE output and upload to Zoho Item Master.
        
        This is the main entry point for the agent.
        
        Args:
            unified_output: Unified output dictionary from output_normalizer
            dry_run: If True, validate but don't actually upload
            
        Returns:
            AgentResult with processing results
        """
        start_time = datetime.now()
        
        # Validate Zoho config
        validate_zoho_config()
        
        logger.info("=" * 60)
        logger.info("ZOHO ITEM MASTER AGENT")
        logger.info("=" * 60)
        logger.info(get_zoho_config_summary())
        
        # Reset state
        self._unified_output = unified_output
        self._discovered_fields = {}
        self._category_map = {}
        self._results = []
        self._agent_complete = False
        self._items_uploaded = 0

        products = unified_output.get("products", [])
        self._total_items = len(products)
        client_info = unified_output.get("client", {})
        metadata = unified_output.get("metadata", {})
        
        logger.info(f"Source: {metadata.get('source', 'unknown')}")
        logger.info(f"Products to process: {len(products)}")
        logger.info(f"Client: {client_info.get('name') or client_info.get('company', 'Unknown')}")
        
        if dry_run:
            logger.info("[DRY RUN] Would process items but not upload to Zoho")
            return AgentResult(
                success=True,
                total_products=len(products),
                successful_uploads=0,
                failed_uploads=0,
                items=[],
                errors=[{"message": "Dry run - no items uploaded"}]
            )
        
        # Build initial message for Claude
        initial_message = self._build_initial_message(unified_output)
        
        # Run agent loop
        messages = [{"role": "user", "content": initial_message}]
        
        iteration = 0
        while iteration < self.max_iterations and not self._agent_complete:
            iteration += 1
            logger.debug(f"Agent iteration {iteration}")
            
            # Call Claude with extended thinking
            response = self.anthropic.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                thinking={
                    "type": "enabled",
                    "budget_tokens": self.thinking_budget
                },
                system=AGENT_SYSTEM_PROMPT,
                tools=AGENT_TOOLS,
                messages=messages
            )
            
            # Process response
            assistant_content = []
            tool_results = []
            
            for block in response.content:
                if block.type == "thinking":
                    logger.debug(f"Claude thinking: {block.thinking[:200]}...")
                    assistant_content.append(block)
                    
                elif block.type == "text":
                    logger.info(f"Claude: {block.text}")
                    assistant_content.append(block)
                    
                elif block.type == "tool_use":
                    assistant_content.append(block)
                    
                    # Execute tool
                    result = self._handle_tool_call(block.name, block.input)
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            
            # Add assistant message
            messages.append({"role": "assistant", "content": assistant_content})
            
            # Add tool results if any
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            
            # Check stop reason
            if response.stop_reason == "end_turn" and not tool_results:
                logger.info("Agent completed (end_turn)")
                break
        
        # Calculate results
        duration = (datetime.now() - start_time).total_seconds()
        successful = sum(1 for r in self._results if r.success)
        failed = sum(1 for r in self._results if not r.success)
        
        # Build final result
        agent_result = AgentResult(
            success=failed == 0 or successful > 0,  # Success if at least some items uploaded
            total_products=len(products),
            successful_uploads=successful,
            failed_uploads=failed,
            items=self._results,
            client_account_number=None,  # Will be set from search if found
            discovered_custom_fields=self._discovered_fields,
            errors=[{"item": r.zoho_sku, "error": r.error} for r in self._results if not r.success],
            duration_seconds=duration
        )
        
        # Log summary
        logger.info("=" * 60)
        logger.info("AGENT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total Products: {agent_result.total_products}")
        logger.info(f"Successful: {agent_result.successful_uploads}")
        logger.info(f"Failed: {agent_result.failed_uploads}")
        logger.info(f"Duration: {agent_result.duration_seconds:.2f}s")
        
        return agent_result
    
    def _get_client_email_instruction(self) -> str:
        """Get instruction for client email lookup if available."""
        if self.client_email:
            return f"""
## **IMPORTANT: Client Email for Contact Lookup**
Use this email address to search for the Zoho contact: **{self.client_email}**
Search using the `search_contact` tool with this email to find the correct client account number for SKU prefixes.

"""
        return ""

    def _build_initial_message(self, unified_output: Dict[str, Any]) -> str:
        """Build the initial message for Claude with unified output context."""
        products = unified_output.get("products", [])
        client = unified_output.get("client", {})
        presenter = unified_output.get("presenter", {})
        metadata = unified_output.get("metadata", {})
        
        # Build product summary
        product_summaries = []
        for i, product in enumerate(products):
            item = product.get("item", {})
            identifiers = product.get("identifiers", {})
            images = product.get("images", [])
            
            summary = f"""
Product {i}: {item.get('name', 'Unknown')}
- Vendor SKU: {identifiers.get('vendor_sku') or identifiers.get('mpn') or 'N/A'}
- CPN: {identifiers.get('cpn') or 'N/A'}
- Categories: {', '.join(item.get('categories', [])) or 'None'}
- Has Images: {len(images) > 0}
"""
            product_summaries.append(summary)
        
        message = f"""
# Unified Output to Process

## Metadata
- Source Platform: {metadata.get('source', 'unknown')}
- Presentation URL: {metadata.get('presentation_url', 'N/A')}
- Presentation Title: {metadata.get('presentation_title', 'N/A')}
- Total Products: {len(products)}

## Client Information
- Name: {client.get('name') or 'N/A'}
- Company: {client.get('company') or 'N/A'}
- Email: {client.get('email') or 'N/A'}

## Presenter Information
- Name: {presenter.get('name') or 'N/A'}
- Company: {presenter.get('company') or 'N/A'}
{self._get_client_email_instruction()}
## Products to Upload
{"".join(product_summaries)}

---

Please process all {len(products)} product(s) according to the workflow:
1. Search for the client contact to get their account number
2. Discover available custom fields
3. Optionally get categories
4. Upsert each product to Zoho Item Master
5. Upload images for products that have them
6. Report completion when done

Begin processing.
"""
        return message


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for testing the agent."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Zoho Item Master Agent")
    parser.add_argument("input_file", help="Path to unified JSON output file")
    parser.add_argument("--dry-run", action="store_true", help="Validate without uploading")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('zoho_agent.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Load input file
    with open(args.input_file, 'r') as f:
        unified_output = json.load(f)
    
    # Create and run agent
    agent = ZohoItemMasterAgent()
    result = agent.process_unified_output(unified_output, dry_run=args.dry_run)
    
    # Output result
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"Success: {result.success}")
    print(f"Total Products: {result.total_products}")
    print(f"Successful Uploads: {result.successful_uploads}")
    print(f"Failed Uploads: {result.failed_uploads}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")
    
    # Exit code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
