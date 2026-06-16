"""SAGE pipeline components for viewpresentation.com presentations."""

from promo_parser.pipelines.sage.handler import SAGEHandler
from promo_parser.pipelines.sage.scraper import Presentation, scrape

__all__ = [
    "SAGEHandler",
    "Presentation",
    "scrape",
]
