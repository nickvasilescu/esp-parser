#!/usr/bin/env python3
"""
Orgo File Handler
=================

Handles file operations via Orgo's File Export API.
Replaces S3Handler for retrieving files from Orgo VMs.

Usage:
    from orgo_file_handler import OrgoFileHandler

    handler = OrgoFileHandler(job_id, computer_id, orgo_api_key)

    # Export and download presentation PDF
    handler.download_presentation(local_path)

    # Export and download product PDF
    handler.download_product_pdf(cpn, local_path)
"""

import base64
import logging
import os
from pathlib import Path
from typing import Optional

import requests

# Import orgo Computer for bash fallback
try:
    from orgo import Computer
    ORGO_AVAILABLE = True
except ImportError:
    ORGO_AVAILABLE = False
    Computer = None

logger = logging.getLogger(__name__)

# Orgo API base URL
ORGO_API_URL = "https://www.orgo.ai/api"


class OrgoFileHandler:
    """
    Handles file operations via Orgo's File Export API.

    Files are stored on the Orgo VM at ~/Downloads/{job_id}/
    and exported via the Orgo API to get temporary download URLs.
    """

    def __init__(
        self,
        job_id: str,
        computer_id: str,
        orgo_api_key: Optional[str] = None
    ):
        """
        Initialize the Orgo File Handler.

        Args:
            job_id: Unique job identifier for organizing files
            computer_id: Orgo computer/desktop ID
            orgo_api_key: Orgo API key (defaults to ORGO_API_KEY env var)
        """
        self.job_id = job_id
        self.computer_id = computer_id
        self.orgo_api_key = orgo_api_key or os.getenv("ORGO_API_KEY", "")

        if not self.orgo_api_key:
            logger.warning("ORGO_API_KEY not set - file export will fail")

        # Lazy-loaded Computer instance for bash fallback
        self._computer: Optional[Computer] = None

    def _get_computer(self) -> Optional[Computer]:
        """Get or create Computer instance for bash operations."""
        if not ORGO_AVAILABLE:
            logger.warning("orgo package not available for bash fallback")
            return None
        if self._computer is None:
            self._computer = Computer(computer_id=self.computer_id)
        return self._computer

    def _get_headers(self) -> dict:
        """Get headers for Orgo API requests."""
        return {
            "Authorization": f"Bearer {self.orgo_api_key}",
            "Content-Type": "application/json"
        }

    def export_file(self, remote_path: str) -> Optional[str]:
        """
        Export a file from the VM using Orgo's File Export API.

        The path should be relative to the user's home directory,
        e.g., "Downloads/{job_id}/presentation.pdf"

        Args:
            remote_path: Path to the file on the VM (relative to home)

        Returns:
            Temporary download URL for the file, or None if export failed
        """
        # Try both relative and absolute paths
        # API accepts: 'Desktop/results.txt' or '/home/user/Desktop/results.txt'
        paths_to_try = [
            remote_path,  # Relative path first
            f"/home/user/{remote_path}",  # Absolute path as fallback
        ]

        last_error = None
        for path in paths_to_try:
            logger.info(f"Exporting file from VM: {path}")

            try:
                response = requests.post(
                    f"{ORGO_API_URL}/files/export",
                    headers=self._get_headers(),
                    json={
                        "desktopId": self.computer_id,
                        "path": path
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        download_url = data.get("url")
                        logger.info(f"File exported successfully: {path}")
                        logger.debug(f"Download URL: {download_url[:100]}...")
                        return download_url
                    else:
                        last_error = data.get("error", "Unknown error")
                        logger.warning(f"File export failed for path {path}: {last_error}")
                        continue  # Try next path
                else:
                    last_error = f"{response.status_code} - {response.text}"
                    logger.warning(f"File export request failed for path {path}: {last_error}")
                    continue  # Try next path

            except requests.exceptions.Timeout:
                last_error = "Timeout"
                logger.warning(f"File export timed out for path {path}")
                continue
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                logger.warning(f"File export request error for path {path}: {e}")
                continue
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Unexpected error during file export for path {path}: {e}")
                continue

        # All paths failed
        logger.error(f"File export failed for all paths. Last error: {last_error}")
        return None

    def download_file_via_bash(self, remote_path: str, local_path: str) -> str:
        """
        Download a file from the VM using base64 encoding via bash.

        This is a fallback method when the Orgo File Export API fails.
        It uses the orgo Computer's bash() method to base64 encode the file
        and transfer it in chunks.

        Args:
            remote_path: Path to the file on the VM (relative to home, e.g., "Downloads/job_id/file.pdf")
            local_path: Local path to save the file

        Returns:
            The local path where the file was saved

        Raises:
            FileNotFoundError: If the file doesn't exist on the VM
            IOError: If the transfer failed
        """
        computer = self._get_computer()
        if not computer:
            raise IOError("orgo package not available for bash fallback")

        # Use absolute path
        abs_path = f"/home/user/{remote_path}"

        # Check if file exists and get size
        logger.info(f"Checking file on VM: {abs_path}")
        try:
            size_output = computer.bash(f'stat -c %s "{abs_path}" 2>/dev/null || echo "NOT_FOUND"')
            if "NOT_FOUND" in size_output or not size_output.strip():
                raise FileNotFoundError(f"File not found on VM: {abs_path}")

            file_size = int(size_output.strip())
            logger.info(f"File size: {file_size} bytes")
        except Exception as e:
            if "NOT_FOUND" in str(e):
                raise FileNotFoundError(f"File not found on VM: {abs_path}")
            raise IOError(f"Failed to check file: {e}")

        # For files up to ~5MB, transfer in one chunk
        # For larger files, split into chunks
        CHUNK_SIZE = 1024 * 1024 * 2  # 2MB chunks (will be ~2.7MB base64)

        # Ensure parent directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        if file_size <= CHUNK_SIZE * 2:
            # Small file - transfer in one go
            logger.info("Transferring file via base64 (single chunk)...")
            try:
                b64_output = computer.bash(f'base64 "{abs_path}"')
                file_data = base64.b64decode(b64_output)

                with open(local_path, 'wb') as f:
                    f.write(file_data)

                logger.info(f"Downloaded {len(file_data)} bytes to: {local_path}")
                return local_path
            except Exception as e:
                raise IOError(f"Base64 transfer failed: {e}")
        else:
            # Large file - transfer in chunks
            logger.info(f"Transferring large file via base64 ({file_size} bytes in chunks)...")
            try:
                with open(local_path, 'wb') as f:
                    offset = 0
                    chunk_num = 0
                    while offset < file_size:
                        chunk_num += 1
                        # Use dd to read specific chunk and base64 encode
                        cmd = f'dd if="{abs_path}" bs={CHUNK_SIZE} skip={chunk_num - 1} count=1 2>/dev/null | base64'
                        b64_chunk = computer.bash(cmd)

                        if not b64_chunk.strip():
                            break

                        chunk_data = base64.b64decode(b64_chunk)
                        f.write(chunk_data)
                        offset += len(chunk_data)
                        logger.info(f"  Chunk {chunk_num}: {len(chunk_data)} bytes (total: {offset}/{file_size})")

                logger.info(f"Downloaded {offset} bytes to: {local_path}")
                return local_path
            except Exception as e:
                raise IOError(f"Chunked base64 transfer failed: {e}")

    def download_file(self, remote_path: str, local_path: str) -> str:
        """
        Export a file from the VM and download it to a local path.

        Tries the Orgo File Export API first, then falls back to base64 transfer
        via bash if the API fails.

        Args:
            remote_path: Path to the file on the VM (relative to home)
            local_path: Local path to save the file

        Returns:
            The local path where the file was saved

        Raises:
            FileNotFoundError: If the file could not be exported
            IOError: If the download or save failed
        """
        # Try 1: Orgo File Export API
        download_url = self.export_file(remote_path)

        if download_url:
            # Download the file from the export URL
            logger.info(f"Downloading via Orgo API to: {local_path}")

            try:
                response = requests.get(download_url, timeout=60)
                response.raise_for_status()

                # Ensure parent directory exists
                Path(local_path).parent.mkdir(parents=True, exist_ok=True)

                # Save to file
                with open(local_path, 'wb') as f:
                    f.write(response.content)

                file_size = len(response.content)
                logger.info(f"Downloaded {file_size} bytes to: {local_path}")

                return local_path

            except requests.exceptions.RequestException as e:
                logger.warning(f"API download failed, trying bash fallback: {e}")
            except IOError as e:
                logger.warning(f"Save failed, trying bash fallback: {e}")

        # Try 2: Fallback to base64 transfer via bash
        logger.info("Orgo File Export API failed, using bash fallback...")
        return self.download_file_via_bash(remote_path, local_path)

    def export_presentation(self) -> Optional[str]:
        """
        Export the presentation PDF and return its download URL.

        Returns:
            Download URL for the presentation PDF, or None if export failed
        """
        return self.export_file(f"Downloads/{self.job_id}/presentation.pdf")

    def download_presentation(self, local_path: str) -> str:
        """
        Export and download the presentation PDF.

        Args:
            local_path: Local path to save the presentation PDF

        Returns:
            The local path where the file was saved
        """
        return self.download_file(
            f"Downloads/{self.job_id}/presentation.pdf",
            local_path
        )

    def export_product_pdf(self, cpn: str) -> Optional[str]:
        """
        Export a product's distributor report PDF and return its download URL.

        Args:
            cpn: Customer Product Number (e.g., "CPN-564493187")

        Returns:
            Download URL for the product PDF, or None if export failed
        """
        return self.export_file(
            f"Downloads/{self.job_id}/{cpn}_distributor_report.pdf"
        )

    def download_product_pdf(self, cpn: str, local_path: str) -> str:
        """
        Export and download a product's distributor report PDF.

        Args:
            cpn: Customer Product Number (e.g., "CPN-564493187")
            local_path: Local path to save the product PDF

        Returns:
            The local path where the file was saved
        """
        return self.download_file(
            f"Downloads/{self.job_id}/{cpn}_distributor_report.pdf",
            local_path
        )

    def list_job_files(self) -> list:
        """
        List all files in the job directory on the VM.

        Note: This uses the Orgo files/list API if available.

        Returns:
            List of file paths in the job directory
        """
        try:
            response = requests.post(
                f"{ORGO_API_URL}/files/list",
                headers=self._get_headers(),
                json={
                    "desktopId": self.computer_id,
                    "path": f"Downloads/{self.job_id}"
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("files", [])

            logger.warning(f"Could not list files: {response.status_code}")
            return []

        except Exception as e:
            logger.warning(f"Error listing files: {e}")
            return []


# =============================================================================
# CLI Entry Point for Testing
# =============================================================================

def main():
    """CLI entry point for testing the file handler."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test Orgo File Handler"
    )
    parser.add_argument(
        "action",
        choices=["export", "download", "list"],
        help="Action to perform"
    )
    parser.add_argument(
        "--job-id",
        type=str,
        required=True,
        help="Job ID"
    )
    parser.add_argument(
        "--computer-id",
        type=str,
        required=True,
        help="Orgo computer ID"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="File path (for export/download)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path (for download)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create handler
    handler = OrgoFileHandler(
        job_id=args.job_id,
        computer_id=args.computer_id
    )

    if args.action == "export":
        if not args.file:
            print("Error: --file required for export")
            return 1
        url = handler.export_file(args.file)
        if url:
            print(f"Export URL: {url}")
            return 0
        else:
            print("Export failed")
            return 1

    elif args.action == "download":
        if not args.file or not args.output:
            print("Error: --file and --output required for download")
            return 1
        try:
            path = handler.download_file(args.file, args.output)
            print(f"Downloaded to: {path}")
            return 0
        except Exception as e:
            print(f"Download failed: {e}")
            return 1

    elif args.action == "list":
        files = handler.list_job_files()
        print(f"Files in job {args.job_id}:")
        for f in files:
            print(f"  - {f}")
        return 0


if __name__ == "__main__":
    exit(main())
