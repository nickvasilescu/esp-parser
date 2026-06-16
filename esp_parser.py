#!/usr/bin/env python3
"""
ESP PDF Parser - Extract structured product data from ESP+ sell sheets using Claude Opus 4.5.

This module is a thin wrapper around pdf_processor.py for backward compatibility.
It uses the EXTRACTION_PROMPT from prompt.py to parse product sell sheets.

Usage:
    python esp_parser.py -f product.pdf              # Single file, output to both stdout and file
    python esp_parser.py -d ./pdfs/ -o file          # Directory of PDFs, output to files only
    python esp_parser.py -f product.pdf -o stdout    # Single file, stdout only
"""

import argparse
import json
import os
import sys
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from prompt import EXTRACTION_PROMPT
from pdf_processor import (
    process_pdf,
    save_json_output,
    process_directory as _process_directory
)


def parse_pdf(pdf_path: str, client: Anthropic) -> dict:
    """
    Parse a single PDF file using Claude Opus 4.5 and return the extracted JSON.
    
    This is a convenience wrapper that uses the standard EXTRACTION_PROMPT
    for product sell sheets.
    
    Args:
        pdf_path: Path to the PDF file
        client: Anthropic API client
        
    Returns:
        Parsed JSON data as a dictionary
        
    Raises:
        ValueError: If the API response cannot be parsed as JSON
        FileNotFoundError: If the PDF file doesn't exist
    """
    return process_pdf(pdf_path, client, EXTRACTION_PROMPT)


def save_output(data: dict, pdf_path: str, output_dir: Optional[str] = None) -> str:
    """
    Save extracted JSON data to a file.
    
    Args:
        data: The extracted data dictionary
        pdf_path: Original PDF file path (used to derive output filename)
        output_dir: Optional custom output directory
        
    Returns:
        Path to the saved JSON file
    """
    return save_json_output(data, pdf_path, output_dir)


def process_directory(
    dir_path: str,
    client: Anthropic,
    output_mode: str,
    output_dir: Optional[str] = None
) -> list:
    """
    Process all PDF files in a directory.
    
    Args:
        dir_path: Path to directory containing PDFs
        client: Anthropic API client
        output_mode: One of 'stdout', 'file', or 'both'
        output_dir: Optional custom output directory for JSON files
        
    Returns:
        List of results (each with 'file', 'success', 'data' or 'error')
    """
    return _process_directory(
        dir_path, 
        client, 
        EXTRACTION_PROMPT, 
        output_mode, 
        output_dir
    )


def main():
    """Main entry point for the CLI."""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Extract structured product data from ESP+ PDF sell sheets using Claude Opus 4.5.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -f product.pdf                    # Single file, output to stdout and file
  %(prog)s -f product.pdf -o stdout          # Single file, stdout only
  %(prog)s -f product.pdf -o file            # Single file, save to JSON only
  %(prog)s -d ./pdfs/ -o both                # Process directory, output both
  %(prog)s -d ./pdfs/ --output-dir ./output  # Process directory, save to custom dir

Environment:
  ANTHROPIC_API_KEY    Your Anthropic API key (required)
        """
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-f", "--file",
        type=str,
        help="Path to a single PDF file to process"
    )
    input_group.add_argument(
        "-d", "--directory",
        type=str,
        help="Path to a directory containing PDF files to process"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        choices=["stdout", "file", "both"],
        default="both",
        help="Output mode: 'stdout' (print JSON), 'file' (save to .json), or 'both' (default: both)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Custom output directory for JSON files (default: same as input)"
    )
    
    args = parser.parse_args()
    
    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        print("Set it with: export ANTHROPIC_API_KEY='your-api-key'", file=sys.stderr)
        sys.exit(1)
    
    # Initialize Anthropic client
    client = Anthropic(api_key=api_key)
    
    try:
        if args.file:
            # Process single file
            print(f"Processing: {args.file}...", file=sys.stderr)
            data = parse_pdf(args.file, client)
            
            if args.output in ("stdout", "both"):
                print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if args.output in ("file", "both"):
                saved_path = save_output(data, args.file, args.output_dir)
                print(f"Saved to: {saved_path}", file=sys.stderr)
            
        else:
            # Process directory
            results = process_directory(
                args.directory,
                client,
                args.output,
                args.output_dir
            )
            
            # Summary
            success_count = sum(1 for r in results if r["success"])
            print(f"\nProcessed {len(results)} files: {success_count} succeeded, {len(results) - success_count} failed", file=sys.stderr)
            
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

