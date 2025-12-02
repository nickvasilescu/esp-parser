#!/usr/bin/env python3
"""
ESP PDF Parser - Extract structured product data from ESP+ sell sheets using Claude Opus 4.5.

Usage:
    python esp_parser.py -f product.pdf              # Single file, output to both stdout and file
    python esp_parser.py -d ./pdfs/ -o file          # Directory of PDFs, output to files only
    python esp_parser.py -f product.pdf -o stdout    # Single file, stdout only
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv

from prompt import EXTRACTION_PROMPT


def load_pdf_as_base64(pdf_path: str) -> str:
    """Read a PDF file and return its base64-encoded content."""
    with open(pdf_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def parse_pdf(pdf_path: str, client: Anthropic) -> dict:
    """
    Parse a single PDF file using Claude Opus 4.5 and return the extracted JSON.
    
    Args:
        pdf_path: Path to the PDF file
        client: Anthropic API client
        
    Returns:
        Parsed JSON data as a dictionary
        
    Raises:
        ValueError: If the API response cannot be parsed as JSON
        FileNotFoundError: If the PDF file doesn't exist
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    pdf_base64 = load_pdf_as_base64(pdf_path)
    
    response = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=8192,
        system=EXTRACTION_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64
                        }
                    }
                ]
            }
        ]
    )
    
    # Extract text content from response
    response_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            response_text += block.text
    
    # Parse the JSON response
    try:
        # Try to find JSON in the response (in case there's any extra text)
        response_text = response_text.strip()
        
        # If response starts with ```, try to extract JSON from code block
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```") and not in_json:
                    in_json = True
                    continue
                elif line.startswith("```") and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)
        
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse API response as JSON: {e}\nResponse: {response_text[:500]}...")


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
    pdf_path = Path(pdf_path)
    
    if output_dir:
        output_path = Path(output_dir) / f"{pdf_path.stem}.json"
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = pdf_path.with_suffix(".json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return str(output_path)


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
    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a valid directory: {dir_path}")
    
    pdf_files = list(dir_path.glob("*.pdf")) + list(dir_path.glob("*.PDF"))
    
    if not pdf_files:
        print(f"No PDF files found in {dir_path}", file=sys.stderr)
        return []
    
    results = []
    total = len(pdf_files)
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"Processing [{i}/{total}]: {pdf_file.name}...", file=sys.stderr)
        
        result = {"file": str(pdf_file), "success": False}
        
        try:
            data = parse_pdf(str(pdf_file), client)
            result["success"] = True
            result["data"] = data
            
            # Handle output based on mode
            if output_mode in ("stdout", "both"):
                print(f"\n--- {pdf_file.name} ---")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if output_mode in ("file", "both"):
                saved_path = save_output(data, str(pdf_file), output_dir)
                print(f"  Saved to: {saved_path}", file=sys.stderr)
                result["output_file"] = saved_path
                
        except Exception as e:
            result["error"] = str(e)
            print(f"  Error: {e}", file=sys.stderr)
        
        results.append(result)
    
    return results


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

