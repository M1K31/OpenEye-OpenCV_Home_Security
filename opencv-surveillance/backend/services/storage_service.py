# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Cloud Storage Service for OpenEye
Supports multiple cloud storage providers: AWS S3, Google Cloud Storage, Azure Blob Storage
"""

import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)


class CloudStorageService:
    """
    Manages cloud storage for recordings and snapshots
    Supports: AWS S3, Google Cloud Storage, Azure Blob Storage
    """
    
    def __init__(
        self,
        provider: str = "s3",
        bucket_name: str = None,
        **credentials
    ):
        """
        Initialize cloud storage service
        
        Args:
            provider: Storage provider (s3, gcs, azure)
            bucket_name: Bucket/container name
            **credentials: Provider-specific credentials
        """
        self.provider = provider.lower()
        self.bucket_name = bucket_name
        self.client = None
        
        if provider == "s3":
            self._init_s3(**credentials)
        elif provider == "gcs":
            self._init_gcs(**credentials)
        elif provider == "azure":
            self._init_azure(**credentials)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        
        logger.info(f"Cloud storage initialized: {provider}")
    
    def _init_s3(
        self,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        region_name: str = "us-east-1",
        **kwargs
    ):
        """Initialize AWS S3 client"""
        try:
            import boto3
            self.client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id or os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=aws_secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=region_name
            )
            logger.info("AWS S3 client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize S3: {e}")
            raise
    
    def _init_gcs(
        self,
        credentials_path: str = None,
        project_id: str = None,
        **kwargs
    ):
        """Initialize Google Cloud Storage client"""
        try:
            from google.cloud import storage as gcs
            if credentials_path:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            
            self.client = gcs.Client(project=project_id)
            logger.info("Google Cloud Storage client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GCS: {e}")
            raise
    
    def _init_azure(
        self,
        connection_string: str = None,
        **kwargs
    ):
        """Initialize Azure Blob Storage client"""
        try:
            from azure.storage.blob import BlobServiceClient
            
            self.client = BlobServiceClient.from_connection_string(
                connection_string or os.getenv('AZURE_STORAGE_CONNECTION_STRING')
            )
            logger.info("Azure Blob Storage client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Azure: {e}")
            raise
    
    async def upload_file(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Upload file to cloud storage
        
        Args:
            local_path: Path to local file
            remote_path: Destination path in cloud
            metadata: Optional metadata dictionary
            
        Returns:
            True if successful
        """
        try:
            if self.provider == "s3":
                return await self._upload_s3(local_path, remote_path, metadata)
            elif self.provider == "gcs":
                return await self._upload_gcs(local_path, remote_path, metadata)
            elif self.provider == "azure":
                return await self._upload_azure(local_path, remote_path, metadata)
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False
    
    async def _upload_s3(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Upload to S3"""
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.upload_file(
                    local_path,
                    self.bucket_name,
                    remote_path,
                    ExtraArgs=extra_args
                )
            )
            
            logger.info(f"Uploaded to S3: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"S3 upload error: {e}")
            return False
    
    async def _upload_gcs(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Upload to Google Cloud Storage"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(remote_path)
            
            if metadata:
                blob.metadata = metadata
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                blob.upload_from_filename,
                local_path
            )
            
            logger.info(f"Uploaded to GCS: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"GCS upload error: {e}")
            return False
    
    async def _upload_azure(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Upload to Azure Blob Storage"""
        try:
            blob_client = self.client.get_blob_client(
                container=self.bucket_name,
                blob=remote_path
            )
            
            with open(local_path, "rb") as data:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: blob_client.upload_blob(data, metadata=metadata, overwrite=True)
                )
            
            logger.info(f"Uploaded to Azure: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"Azure upload error: {e}")
            return False
    
    def generate_presigned_url(
        self,
        remote_path: str,
        expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned URL for file access
        
        Args:
            remote_path: Path to file in cloud
            expiration: URL expiration time in seconds
            
        Returns:
            Presigned URL or None if error
        """
        try:
            if self.provider == "s3":
                url = self.client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': remote_path
                    },
                    ExpiresIn=expiration
                )
                return url
            
            elif self.provider == "gcs":
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(remote_path)
                url = blob.generate_signed_url(
                    expiration=timedelta(seconds=expiration)
                )
                return url
            
            elif self.provider == "azure":
                from azure.storage.blob import generate_blob_sas, BlobSasPermissions
                
                sas_token = generate_blob_sas(
                    account_name=self.client.account_name,
                    container_name=self.bucket_name,
                    blob_name=remote_path,
                    account_key=self.client.credential.account_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(seconds=expiration)
                )
                
                url = f"https://{self.client.account_name}.blob.core.windows.net/{self.bucket_name}/{remote_path}?{sas_token}"
                return url
            
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None
    
    async def delete_file(self, remote_path: str) -> bool:
        """
        Delete file from cloud storage
        
        Args:
            remote_path: Path to file in cloud
            
        Returns:
            True if successful
        """
        try:
            if self.provider == "s3":
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.client.delete_object(Bucket=self.bucket_name, Key=remote_path)
                )
            
            elif self.provider == "gcs":
                bucket = self.client.bucket(self.bucket_name)
                blob = bucket.blob(remote_path)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, blob.delete)
            
            elif self.provider == "azure":
                blob_client = self.client.get_blob_client(
                    container=self.bucket_name,
                    blob=remote_path
                )
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, blob_client.delete_blob)
            
            logger.info(f"Deleted from cloud: {remote_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False


# Global instance
_storage_service: Optional[CloudStorageService] = None


def get_storage_service() -> Optional[CloudStorageService]:
    """Get or create cloud storage service instance"""
    global _storage_service
    return _storage_service


def initialize_storage_service(
    provider: str,
    bucket_name: str,
    **credentials
) -> CloudStorageService:
    """Initialize cloud storage service"""
    global _storage_service
    _storage_service = CloudStorageService(provider, bucket_name, **credentials)
    return _storage_service
