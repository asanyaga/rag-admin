"""Parsing adapters for document processing."""
from app.adapters.parsing.registry import get_parser, get_available_parsers

__all__ = ["get_parser", "get_available_parsers"]
