#!/usr/bin/env python3
"""
S3 Handler for ESP-Orgo CUA Orchestration.
Manages file uploads and downloads via AWS S3 using pre-signed URLs.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    AWS_S3_BUCKET,
)

logger = logging.getLogger(__name__)


# =============================================================================
# S3 Handler Class
# =============================================================================

class S3Handler:
    """
    Handles S3 operations for the CUA pipeline.
    
    Uses a job_id to organize files into virtual "folders" in S3:
        s3://<bucket>/<job_id>/presentation.pdf
        s3://<bucket>/<job_id>/products/<CPN>_distributor_report.pdf
    """
    
    def __init__(self, job_id: Optional[str] = None):
        """
        Initialize the S3 handler.
        
        Args:
            job_id: Unique identifier for this job run.
                    If not provided, generates one based on timestamp.
        """
        self.job_id = job_id or self._generate_job_id()
        self.bucket = AWS_S3_BUCKET
        self.region = AWS_REGION
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
            config=Config(signature_version='s3v4')
        )
        
        logger.info(f"S3Handler initialized for job: {self.job_id}")
        logger.info(f"Bucket: {self.bucket}, Region: {self.region}")
    
    def _generate_job_id(self) -> str:
        """Generate a unique job ID based on timestamp."""
        return f"esp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _get_full_key(self, filename: str) -> str:
        """
        Get the full S3 key (path) for a file within this job's folder.
        
        Args:
            filename: The filename or relative path (e.g., "presentation.pdf" 
                      or "products/CPN-123_report.pdf")
        
        Returns:
            Full S3 key like "esp_20250603_1430/presentation.pdf"
        """
        return f"{self.job_id}/{filename}"
    
    # =========================================================================
    # Pre-signed URL Generation
    # =========================================================================
    
    def generate_presigned_upload_url(
        self,
        filename: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate a pre-signed URL for uploading a file to S3.
        
        The agent can use this URL with curl:
            curl -X PUT -T <local_file> "<presigned_url>"
        
        Args:
            filename: The filename or relative path within the job folder.
            expiration: URL expiration time in seconds (default: 1 hour).
        
        Returns:
            Pre-signed URL string for PUT operation.
        """
        key = self._get_full_key(filename)
        
        try:
            url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': key,
                    'ContentType': 'application/pdf'
                },
                ExpiresIn=expiration
            )
            logger.info(f"Generated upload URL for: {key}")
            return url
        except ClientError as e:
            logger.error(f"Failed to generate upload URL for {key}: {e}")
            raise
    
    def generate_presigned_download_url(
        self,
        filename: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate a pre-signed URL for downloading a file from S3.
        
        Args:
            filename: The filename or relative path within the job folder.
            expiration: URL expiration time in seconds (default: 1 hour).
        
        Returns:
            Pre-signed URL string for GET operation.
        """
        key = self._get_full_key(filename)
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': key
                },
                ExpiresIn=expiration
            )
            logger.info(f"Generated download URL for: {key}")
            return url
        except ClientError as e:
            logger.error(f"Failed to generate download URL for {key}: {e}")
            raise
    
    def generate_product_upload_urls(
        self,
        cpns: List[str],
        expiration: int = 3600
    ) -> Dict[str, str]:
        """
        Generate pre-signed upload URLs for multiple product PDFs.
        
        Args:
            cpns: List of CPNs (Customer Product Numbers).
            expiration: URL expiration time in seconds.
        
        Returns:
            Dictionary mapping CPN to pre-signed upload URL.
            Example: {"CPN-123": "https://...", "CPN-456": "https://..."}
        """
        url_map = {}
        for cpn in cpns:
            filename = f"products/{cpn}_distributor_report.pdf"
            url_map[cpn] = self.generate_presigned_upload_url(filename, expiration)
        
        logger.info(f"Generated {len(url_map)} product upload URLs")
        return url_map
    
    # =========================================================================
    # File Download Operations
    # =========================================================================
    
    def download_file(self, filename: str, local_path: str) -> str:
        """
        Download a specific file from S3 to a local path.
        
        Args:
            filename: The filename or relative path within the job folder.
            local_path: Local file path to save the downloaded file.
        
        Returns:
            The local path where the file was saved.
        """
        key = self._get_full_key(filename)
        
        # Ensure local directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info(f"Downloading s3://{self.bucket}/{key} -> {local_path}")
            self.s3_client.download_file(self.bucket, key, local_path)
            logger.info(f"Downloaded: {local_path}")
            return local_path
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == '404':
                logger.warning(f"File not found in S3: {key}")
                raise FileNotFoundError(f"S3 file not found: {key}")
            logger.error(f"Failed to download {key}: {e}")
            raise
    
    def download_directory(
        self,
        prefix: str,
        local_dir: str
    ) -> List[str]:
        """
        Download all files with a given prefix from the job folder.
        
        Args:
            prefix: The prefix/subdirectory within the job folder (e.g., "products").
            local_dir: Local directory to save the downloaded files.
        
        Returns:
            List of local file paths that were downloaded.
        """
        full_prefix = self._get_full_key(prefix)
        
        # Ensure local directory exists
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        
        downloaded_files = []
        
        try:
            # List objects with the given prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket, Prefix=full_prefix)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    key = obj['Key']
                    # Extract filename from key (remove job_id prefix)
                    relative_path = key.replace(f"{self.job_id}/", "", 1)
                    local_path = os.path.join(local_dir, os.path.basename(relative_path))
                    
                    logger.info(f"Downloading s3://{self.bucket}/{key} -> {local_path}")
                    self.s3_client.download_file(self.bucket, key, local_path)
                    downloaded_files.append(local_path)
            
            logger.info(f"Downloaded {len(downloaded_files)} files from {prefix}/")
            return downloaded_files
            
        except ClientError as e:
            logger.error(f"Failed to download directory {prefix}: {e}")
            raise
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def file_exists(self, filename: str) -> bool:
        """
        Check if a file exists in S3.
        
        Args:
            filename: The filename or relative path within the job folder.
        
        Returns:
            True if file exists, False otherwise.
        """
        key = self._get_full_key(filename)
        
        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def list_files(self, prefix: str = "") -> List[str]:
        """
        List all files in the job folder or a subdirectory.
        
        Args:
            prefix: Optional prefix/subdirectory within the job folder.
        
        Returns:
            List of file keys (relative to job folder).
        """
        full_prefix = self._get_full_key(prefix)
        files = []
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket, Prefix=full_prefix)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    # Return path relative to job folder
                    relative_path = obj['Key'].replace(f"{self.job_id}/", "", 1)
                    files.append(relative_path)
            
            return files
            
        except ClientError as e:
            logger.error(f"Failed to list files: {e}")
            raise
    
    def get_job_summary(self) -> Dict:
        """
        Get a summary of the job's S3 contents.
        
        Returns:
            Dictionary with job info and file counts.
        """
        files = self.list_files()
        product_files = [f for f in files if f.startswith("products/")]
        
        return {
            "job_id": self.job_id,
            "bucket": self.bucket,
            "total_files": len(files),
            "presentation_exists": "presentation.pdf" in files,
            "product_count": len(product_files),
            "files": files
        }


# =============================================================================
# CLI Entry Point (for testing)
# =============================================================================

def main():
    """CLI entry point for testing S3 operations."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test S3 Handler operations")
    parser.add_argument("--job-id", type=str, help="Job ID to use")
    parser.add_argument("--list", action="store_true", help="List files in job folder")
    parser.add_argument("--generate-url", type=str, help="Generate upload URL for filename")
    parser.add_argument("--download", type=str, help="Download file from S3")
    parser.add_argument("--output", type=str, default="./output", help="Output directory")
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize handler
    handler = S3Handler(job_id=args.job_id)
    print(f"Job ID: {handler.job_id}")
    
    if args.list:
        files = handler.list_files()
        print(f"\nFiles in job folder:")
        for f in files:
            print(f"  - {f}")
    
    if args.generate_url:
        url = handler.generate_presigned_upload_url(args.generate_url)
        print(f"\nUpload URL for {args.generate_url}:")
        print(url)
    
    if args.download:
        local_path = os.path.join(args.output, args.download)
        handler.download_file(args.download, local_path)
        print(f"\nDownloaded to: {local_path}")


if __name__ == "__main__":
    main()

