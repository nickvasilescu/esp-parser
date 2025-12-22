"""
promo_parser - ESP/SAGE Promotional Product Presentation Parser

A comprehensive tool for extracting product data from promotional
product presentations and integrating with Zoho Books.
"""

__version__ = "1.0.0"

from promo_parser.pipelines.orchestrator import Orchestrator
from promo_parser.core.config import validate_config, get_config_summary
from promo_parser.core.schema import UnifiedOutput, UnifiedProduct
from promo_parser.core.normalizer import normalize_output

__all__ = [
    "Orchestrator",
    "validate_config",
    "get_config_summary",
    "UnifiedOutput",
    "UnifiedProduct",
    "normalize_output",
]
