#!/usr/bin/env python3
"""
Zoho Quote (Estimate) Creation Agent.

This module implements a Claude agent that creates draft quotes in Zoho Books
from unified ESP/SAGE presentation data.

The agent:
1. Searches Zoho Contacts by account number (STBL-XXXXX format)
2. Links to existing Item Master entries from previous upload
3. Builds quote with structured line items:
   - Product tiers (one per quantity break)
   - Setup fees
   - Decoration options (fan-out approach)
   - Shipping estimate
4. Creates draft quote in Zoho Books

Usage:
    from zoho_quote_agent import ZohoQuoteAgent

    agent = ZohoQuoteAgent()
    result = agent.create_quote(unified_output, item_master_map)
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from promo_parser.integrations.zoho.config import (
    ZOHO_AGENT_MODEL,
    ZOHO_AGENT_THINKING_BUDGET,
    ZOHO_AGENT_MAX_TOKENS,
    ZOHO_AGENT_MAX_ITERATIONS,
    ZOHO_QUOTE_DEFAULTS,
    validate_zoho_config,
)
from promo_parser.integrations.zoho.client import ZohoClient, ZohoAPIError, create_zoho_client
from promo_parser.integrations.zoho.transformer import (
    build_estimate_payload,
    validate_estimate_payload,
    get_vendor_sku,
    extract_numeric_account,
)

# Import JobStateManager for state updates (optional dependency)
try:
    from promo_parser.core.state import JobStateManager, WorkflowStatus
except ImportError:
    JobStateManager = None
    WorkflowStatus = None

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Result Types
# =============================================================================

@dataclass
class QuoteResult:
    """Result of quote creation."""
    success: bool
    estimate_id: Optional[str] = None
    estimate_number: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    total_amount: Optional[float] = None
    line_items_count: int = 0
    error: Optional[str] = None
    duration_seconds: float = 0


# =============================================================================
# Tool Definitions for Claude
# =============================================================================

QUOTE_AGENT_TOOLS = [
    {
        "name": "search_customer_by_account",
        "description": "Search for a customer in Zoho by their account number (contact_number). Account numbers use STBL-XXXXX format (e.g., 'STBL-10040'). Returns the customer_id needed for quote creation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string",
                    "description": "Account number to search for (e.g., '10040' or 'STBL-10040')"
                }
            },
            "required": ["account_number"]
        }
    },
    {
        "name": "search_customer_by_name",
        "description": "Search for a customer in Zoho by name, email, or company. Use this as fallback if account number search fails.",
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
        "name": "get_item_master_entries",
        "description": "Get the Item Master entries that were created in the previous step. Returns a map of SKU -> item_id for linking line items to the Item Master.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "create_draft_quote",
        "description": "Create a draft estimate (quote) in Zoho Books with all line items for products in the presentation. The quote includes: product tiers (one line per quantity break), setup fees, decoration options (fan-out), and shipping.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Zoho customer ID from search_customer"
                }
            },
            "required": ["customer_id"]
        }
    },
    {
        "name": "report_completion",
        "description": "Report that quote creation is complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Summary of what was accomplished"
                },
                "estimate_number": {
                    "type": "string",
                    "description": "Created estimate number for reference"
                }
            },
            "required": ["summary"]
        }
    }
]


# =============================================================================
# Agent System Prompt
# =============================================================================

QUOTE_AGENT_SYSTEM_PROMPT = """You are a Zoho Quote Creation Agent. Your task is to create DRAFT quotes (estimates) in Zoho Books from promotional product presentation data.

## Your Workflow

1. **First**: Search for the customer in Zoho using their account number (STBL-XXXXX format).
   - Extract the account number from the client information in the unified output
   - Use search_customer_by_account with the account number
   - If that fails, try search_customer_by_name as fallback

2. **Second**: Get the Item Master entries that were created in the previous step using get_item_master_entries.
   - This provides SKU -> item_id mapping for linking line items

3. **Third**: Create the draft quote using create_draft_quote with the customer_id.
   - The system automatically builds all line items:
     - Product lines (one per quantity tier from presentation)
     - Setup fee (if exists)
     - Decoration options (fan-out - all options included)
     - Shipping estimate (15% or quoted)

4. **Finally**: Report completion with the estimate number.

## Quote Structure Rules

- **Status**: Always created as DRAFT (not sent to customer)
- **Product Line Items**: One line item per quantity tier (48+, 100+, 250+, etc.)
  - Pricing ALWAYS from presentation sell_price
  - Named as: "Product Name (SKU) - Qty X+"
- **Setup Fee**: Only included if setup fee exists in product data
- **Decoration Options**: Fan-out approach - ALL decoration methods included as separate lines
  - User manually removes unwanted options later
- **Shipping**: 15% of product subtotal OR quoted shipping if available

## Account Number Format

- Account numbers are stored as contact_number in Zoho
- Format: STBL-XXXXX (e.g., "STBL-10040")
- When searching, you can use either "10040" or "STBL-10040"

## Error Handling

- If customer not found by account number, try name/company search
- If customer still not found, report error (cannot create quote without customer)
- If Item Master entries not found, continue (line items can be inline)
- Always report completion even if quote creation fails

## Important Notes

- Quotes are for INTERNAL review (draft status)
- The estimate_number is how Koell finds the quote in Zoho
- Do not mark quote as sent - it stays as draft
"""


# =============================================================================
# Agent Implementation
# =============================================================================

class ZohoQuoteAgent:
    """
    Claude agent for Zoho Quote (Estimate) creation.

    Creates draft quotes from unified presentation data with structured
    line items for products, fees, decoration, and shipping.
    """

    def __init__(
        self,
        zoho_client: Optional[ZohoClient] = None,
        anthropic_client: Optional[Anthropic] = None,
        model: str = ZOHO_AGENT_MODEL,
        thinking_budget: int = ZOHO_AGENT_THINKING_BUDGET,
        max_tokens: int = ZOHO_AGENT_MAX_TOKENS,
        max_iterations: int = ZOHO_AGENT_MAX_ITERATIONS,
        state_manager: Optional["JobStateManager"] = None
    ):
        """
        Initialize the quote agent.

        Args:
            zoho_client: ZohoClient instance (created if not provided)
            anthropic_client: Anthropic client (created if not provided)
            model: Claude model ID
            thinking_budget: Token budget for extended thinking
            max_tokens: Max tokens for responses
            max_iterations: Max tool use iterations
            state_manager: Optional JobStateManager for state updates
        """
        self.zoho_client = zoho_client or create_zoho_client()
        self.anthropic = anthropic_client or Anthropic()
        self.model = model
        self.thinking_budget = thinking_budget
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.state_manager = state_manager

        # State for current processing session
        self._unified_output: Optional[Dict[str, Any]] = None
        self._item_master_map: Dict[str, str] = {}
        self._quote_result: Optional[QuoteResult] = None
        self._agent_complete = False

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
            if tool_name == "search_customer_by_account":
                return self._tool_search_customer_by_account(tool_input)

            elif tool_name == "search_customer_by_name":
                return self._tool_search_customer_by_name(tool_input)

            elif tool_name == "get_item_master_entries":
                return self._tool_get_item_master_entries()

            elif tool_name == "create_draft_quote":
                return self._tool_create_draft_quote(tool_input)

            elif tool_name == "report_completion":
                return self._tool_report_completion(tool_input)

            else:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})

        except Exception as e:
            logger.error(f"Tool error ({tool_name}): {e}")
            return json.dumps({"error": str(e)})

    def _tool_search_customer_by_account(self, tool_input: Dict[str, Any]) -> str:
        """Search for a customer by account number (STBL-XXXXX format)."""
        account_number = tool_input.get("account_number", "")

        if not account_number:
            return json.dumps({
                "found": False,
                "error": "Account number is required"
            })

        # Emit thought for customer search
        if self.state_manager:
            self.state_manager.emit_thought(
                agent="zoho_quote_agent",
                event_type="action",
                content=f"Searching for customer by account: {account_number}"
            )

        customer = self.zoho_client.find_customer_by_account_number(account_number)

        if customer:
            return json.dumps({
                "found": True,
                "customer_id": customer.get("contact_id"),
                "contact_number": customer.get("contact_number"),
                "contact_name": customer.get("contact_name"),
                "company_name": customer.get("company_name"),
                "email": customer.get("email")
            })
        else:
            return json.dumps({
                "found": False,
                "message": f"No customer found with account number: {account_number}. Try search_customer_by_name."
            })

    def _tool_search_customer_by_name(self, tool_input: Dict[str, Any]) -> str:
        """Search for a customer by name, email, or company."""
        search_email = tool_input.get("email")

        contacts = self.zoho_client.search_contacts(
            name=tool_input.get("name"),
            email=search_email,
            company_name=tool_input.get("company_name")
        )

        # Filter to customers only
        customers = [c for c in contacts if c.get("contact_type") == "customer"]

        # CRITICAL: If searching by email, prioritize exact email match
        if search_email and customers:
            exact_email_match = [
                c for c in customers
                if c.get("email", "").lower() == search_email.lower()
            ]
            if exact_email_match:
                logger.info(f"Found exact email match for: {search_email}")
                customers = exact_email_match
            else:
                logger.warning(f"No exact email match for {search_email}, returning first result")

        if customers:
            customer = customers[0]
            logger.info(f"Customer found: {customer.get('contact_name')} ({customer.get('email')})")
            return json.dumps({
                "found": True,
                "customer_id": customer.get("contact_id"),
                "contact_number": customer.get("contact_number"),
                "contact_name": customer.get("contact_name"),
                "company_name": customer.get("company_name"),
                "email": customer.get("email")
            })
        else:
            logger.warning(f"No customer found for search: name={tool_input.get('name')}, email={search_email}")
            return json.dumps({
                "found": False,
                "message": "No matching customer found. Cannot create quote without a customer."
            })

    def _tool_get_item_master_entries(self) -> str:
        """Get Item Master entries from previous upload."""
        if self._item_master_map:
            return json.dumps({
                "success": True,
                "count": len(self._item_master_map),
                "entries": [
                    {"sku": sku, "item_id": iid}
                    for sku, iid in self._item_master_map.items()
                ],
                "message": f"Found {len(self._item_master_map)} Item Master entries for linking"
            })
        else:
            return json.dumps({
                "success": True,
                "count": 0,
                "entries": [],
                "message": "No Item Master entries found. Line items will be created inline (not linked)."
            })

    def _tool_create_draft_quote(self, tool_input: Dict[str, Any]) -> str:
        """Create a draft quote in Zoho Books."""
        customer_id = tool_input.get("customer_id")

        if not customer_id:
            return json.dumps({
                "success": False,
                "error": "customer_id is required"
            })

        if self._unified_output is None:
            return json.dumps({
                "success": False,
                "error": "No unified output loaded"
            })

        try:
            # Emit state: creating quote
            self._update_state(
                WorkflowStatus.ZOHO_CREATING_QUOTE.value if WorkflowStatus else "zoho_creating_quote"
            )

            # Emit thought for quote creation
            if self.state_manager:
                products = self._unified_output.get("products", [])
                self.state_manager.emit_thought(
                    agent="zoho_quote_agent",
                    event_type="action",
                    content=f"Creating draft quote with {len(products)} products"
                )

            # Build the estimate payload
            estimate_payload = build_estimate_payload(
                unified_output=self._unified_output,
                customer_id=customer_id,
                item_master_map=self._item_master_map,
                expiry_days=ZOHO_QUOTE_DEFAULTS.get("expiry_days", 30)
            )

            # Validate
            validation_errors = validate_estimate_payload(estimate_payload)
            if validation_errors:
                return json.dumps({
                    "success": False,
                    "error": f"Validation failed: {', '.join(validation_errors)}"
                })

            # Create in Zoho
            estimate = self.zoho_client.create_estimate(estimate_payload)

            # Store result
            self._quote_result = QuoteResult(
                success=True,
                estimate_id=estimate.get("estimate_id"),
                estimate_number=estimate.get("estimate_number"),
                customer_id=customer_id,
                customer_name=estimate.get("customer_name"),
                total_amount=estimate.get("total"),
                line_items_count=len(estimate_payload.get("line_items", []))
            )

            # Emit success thought
            if self.state_manager:
                self.state_manager.emit_thought(
                    agent="zoho_quote_agent",
                    event_type="success",
                    content=f"Quote created: {estimate.get('estimate_number')} - ${estimate.get('total', 0):.2f}",
                    metadata={"estimate_number": estimate.get("estimate_number"), "total": estimate.get("total")}
                )

            return json.dumps({
                "success": True,
                "estimate_id": estimate.get("estimate_id"),
                "estimate_number": estimate.get("estimate_number"),
                "customer_name": estimate.get("customer_name"),
                "total": estimate.get("total"),
                "line_items_count": len(estimate_payload.get("line_items", [])),
                "status": "draft",
                "expiry_date": estimate.get("expiry_date"),
                "message": f"Draft quote created: {estimate.get('estimate_number')}"
            })

        except ZohoAPIError as e:
            self._quote_result = QuoteResult(
                success=False,
                customer_id=customer_id,
                error=str(e)
            )
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to create quote in Zoho"
            })

    def _tool_report_completion(self, tool_input: Dict[str, Any]) -> str:
        """Mark agent as complete."""
        self._agent_complete = True

        summary = tool_input.get("summary", "Quote processing complete")
        estimate_number = tool_input.get("estimate_number", "")

        return json.dumps({
            "acknowledged": True,
            "summary": summary,
            "estimate_number": estimate_number
        })

    def create_quote(
        self,
        unified_output: Dict[str, Any],
        item_master_map: Optional[Dict[str, str]] = None,
        dry_run: bool = False
    ) -> QuoteResult:
        """
        Create a draft quote in Zoho from unified output.

        This is the main entry point for the quote agent.

        Args:
            unified_output: Unified output dictionary from output_normalizer
            item_master_map: Optional map of SKU -> item_id from Item Master upload
            dry_run: If True, validate but don't actually create

        Returns:
            QuoteResult with creation results
        """
        start_time = datetime.now()

        # Validate Zoho config
        validate_zoho_config()

        logger.info("=" * 60)
        logger.info("ZOHO QUOTE CREATION AGENT")
        logger.info("=" * 60)

        # Reset state
        self._unified_output = unified_output
        self._item_master_map = item_master_map or {}
        self._quote_result = None
        self._agent_complete = False

        products = unified_output.get("products", [])
        client_info = unified_output.get("client", {})
        metadata = unified_output.get("metadata", {})

        logger.info(f"Source: {metadata.get('source', 'unknown')}")
        logger.info(f"Products: {len(products)}")
        logger.info(f"Client: {client_info.get('name') or client_info.get('company', 'Unknown')}")
        logger.info(f"Item Master entries available: {len(self._item_master_map)}")

        if dry_run:
            logger.info("[DRY RUN] Would create quote but not upload to Zoho")

            # Build payload for validation
            estimate_payload = build_estimate_payload(
                unified_output=unified_output,
                customer_id="DRY_RUN_CUSTOMER",
                item_master_map=self._item_master_map
            )

            return QuoteResult(
                success=True,
                line_items_count=len(estimate_payload.get("line_items", [])),
                error="Dry run - quote not created"
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
                system=QUOTE_AGENT_SYSTEM_PROMPT,
                tools=QUOTE_AGENT_TOOLS,
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

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Return result
        if self._quote_result:
            self._quote_result.duration_seconds = duration
            result = self._quote_result
        else:
            result = QuoteResult(
                success=False,
                error="Agent did not complete quote creation",
                duration_seconds=duration
            )

        # Log summary
        logger.info("=" * 60)
        logger.info("QUOTE AGENT COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Success: {result.success}")
        if result.estimate_number:
            logger.info(f"Estimate Number: {result.estimate_number}")
        if result.total_amount:
            logger.info(f"Total Amount: ${result.total_amount:.2f}")
        logger.info(f"Line Items: {result.line_items_count}")
        logger.info(f"Duration: {result.duration_seconds:.2f}s")
        if result.error:
            logger.error(f"Error: {result.error}")

        return result

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
            pricing = product.get("pricing", {})
            breaks = pricing.get("breaks", [])
            fees = product.get("fees", [])

            # Get price tiers
            tier_info = []
            for brk in sorted(breaks, key=lambda b: b.get("quantity", 0)):
                qty = brk.get("quantity", 0)
                sell = brk.get("sell_price")
                if sell:
                    tier_info.append(f"Qty {qty}+: ${sell:.2f}")

            # Get fees
            fee_info = []
            for fee in fees:
                fee_type = fee.get("fee_type", "")
                fee_price = fee.get("list_price")
                if fee_price:
                    fee_info.append(f"{fee_type}: ${fee_price:.2f}")

            summary = f"""
Product {i}: {item.get('name', 'Unknown')}
- SKU: {get_vendor_sku(product) or 'N/A'}
- CPN: {identifiers.get('cpn') or 'N/A'}
- Price Tiers: {', '.join(tier_info) if tier_info else 'No pricing'}
- Fees: {', '.join(fee_info) if fee_info else 'None'}
"""
            product_summaries.append(summary)

        # Extract search hint - prioritize email (most reliable), then account number, then name
        search_hint = ""
        if client.get("email"):
            search_hint = f"**SEARCH BY EMAIL FIRST: {client.get('email')}** (most reliable method)"
        elif client.get("account_number"):
            search_hint = f"Account Number: {client.get('account_number')}"
        elif client.get("name"):
            search_hint = f"(Fallback: Search by name: {client.get('name')})"

        message = f"""
# Quote Creation Request

## Presentation Metadata
- Source Platform: {metadata.get('source', 'unknown')}
- Presentation Title: {metadata.get('presentation_title', 'N/A')}
- Presentation URL: {metadata.get('presentation_url', 'N/A')}

## Client Information
- Name: {client.get('name') or 'N/A'}
- Company: {client.get('company') or 'N/A'}
- Email: {client.get('email') or 'N/A'}
- {search_hint}

## Presenter Information
- Name: {presenter.get('name') or 'N/A'}
- Company: {presenter.get('company') or 'N/A'}

## Products ({len(products)} total)
{"".join(product_summaries)}

## Item Master Entries Available
{len(self._item_master_map)} entries available for linking

---

Please create a DRAFT quote:
1. **CRITICAL**: Search for the customer:
   - **Search by EMAIL FIRST** if available (most reliable - use the email shown above)
   - Only if email search fails, try account number
   - Only as last resort, search by name
   - **VERIFY** the customer's email matches before proceeding
2. Get Item Master entries for linking
3. Create the draft quote with all products and line items
4. Report completion with the estimate number

Begin processing.
"""
        return message


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for testing the quote agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Zoho Quote Creation Agent")
    parser.add_argument("input_file", help="Path to unified JSON output file")
    parser.add_argument("--item-master-file", help="Path to Item Master results JSON (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without creating")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('zoho_quote_agent.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Load input file
    with open(args.input_file, 'r') as f:
        unified_output = json.load(f)

    # Load Item Master map if provided
    item_master_map = {}
    if args.item_master_file:
        with open(args.item_master_file, 'r') as f:
            im_data = json.load(f)
            # Extract SKU -> item_id mapping
            for item in im_data.get("items", []):
                if item.get("zoho_sku") and item.get("item_id"):
                    item_master_map[item["zoho_sku"]] = item["item_id"]

    # Create and run agent
    agent = ZohoQuoteAgent()
    result = agent.create_quote(
        unified_output,
        item_master_map=item_master_map,
        dry_run=args.dry_run
    )

    # Output result
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"Success: {result.success}")
    if result.estimate_number:
        print(f"Estimate Number: {result.estimate_number}")
    if result.estimate_id:
        print(f"Estimate ID: {result.estimate_id}")
    if result.total_amount:
        print(f"Total Amount: ${result.total_amount:.2f}")
    print(f"Line Items: {result.line_items_count}")
    print(f"Duration: {result.duration_seconds:.2f}s")

    if result.error:
        print(f"\nError: {result.error}")

    # Exit code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
