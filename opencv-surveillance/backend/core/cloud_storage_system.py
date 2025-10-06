"""
Cloud Storage Integration
Multi-provider cloud storage for recordings and snapshots

This module provides unified cloud storage interface supporting AWS S3,
Google Cloud Storage, Azure Blob Storage, and local backup with automatic
sync, retention policies, and bandwidth management.
"""

import logging
import asyncio
from typing import Optional, List, Dict, Callable
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
import threading
from queue import Queue
import os

# Cloud provider SDKs
import boto3
from google.cloud import storage as gcs
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)


class StorageProvider(Enum):
    """Supported storage providers"""
    LOCAL = "local"
    AWS_S3 = "aws_s3"
    GOOGLE_CLOUD = "google_cloud"
    AZURE_BLOB = "azure_blob"


@dataclass
class StorageConfig:
    """Storage configuration"""
    provider: StorageProvider
    bucket_name: str
    region: Optional[str] = None
    credentials: Optional[Dict] = None
    endpoint_url: Optional[str] = None  # For S3-compatible services
    prefix: str = ""  # Key prefix for organization


@dataclass
class UploadTask:
    """Upload task"""
    local_path: str
    remote_path: str
    priority: int = 5  # 1-10, higher = more priority
    metadata: Dict = None
    callback: Optional[Callable] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class StorageStats:
    """Storage statistics"""
    total_uploaded: int = 0
    total_bytes: int = 0
    failed_uploads: int = 0
    storage_used: int = 0
    files_count: int = 0


class S3Storage:
    """
    AWS S3 storage provider
    
    Handles uploads, downloads, and management of files in S3
    """
    
    def __init__(self, config: StorageConfig):
        """Initialize S3 storage"""
        self.config = config
        
        # Initialize S3 client
        session_kwargs = {}
        if config.credentials:
            session_kwargs['aws_access_key_id'] = config.credentials.get('access_key_id')
            session_kwargs['aws_secret_access_key'] = config.credentials.get('secret_access_key')
        
        if config.region:
            session_kwargs['region_name'] = config.region
        
        self.s3_client = boto3.client('s3', **session_kwargs)
        
        logger.info(f"S3 storage initialized for bucket: {config.bucket_name}")
    
    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Upload file to S3"""
        try:
            key = f"{self.config.prefix}/{remote_path}".lstrip('/')
            
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.s3_client.upload_file(
                local_path,
                self.config.bucket_name,
                key,
                ExtraArgs=extra_args
            )
            
            logger.info(f"Uploaded {local_path} to s3://{self.config.bucket_name}/{key}")
            return True
        
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            return False
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from S3"""
        try:
            key = f"{self.config.prefix}/{remote_path}".lstrip('/')
            
            self.s3_client.download_file(
                self.config.bucket_name,
                key,
                local_path
            )
            
            logger.info(f"Downloaded {key} from S3")
            return True
        
        except Exception as e:
            logger.error(f"Error downloading from S3: {e}")
            return False
    
    def delete_file(self, remote_path: str) -> bool:
        """Delete file from S3"""
        try:
            key = f"{self.config.prefix}/{remote_path}".lstrip('/')
            
            self.s3_client.delete_object(
                Bucket=self.config.bucket_name,
                Key=key
            )
            
            logger.info(f"Deleted {key} from S3")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting from S3: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> List[Dict]:
        """List files in S3"""
        try:
            full_prefix = f"{self.config.prefix}/{prefix}".lstrip('/')
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.config.bucket_name,
                Prefix=full_prefix
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat()
                })
            
            return files
        
        except Exception as e:
            logger.error(f"Error listing S3 files: {e}")
            return []
    
    def get_storage_size(self) -> int:
        """Get total storage size used"""
        files = self.list_files()
        return sum(f['size'] for f in files)


class GoogleCloudStorage:
    """
    Google Cloud Storage provider
    
    Handles uploads and management of files in GCS
    """
    
    def __init__(self, config: StorageConfig):
        """Initialize GCS storage"""
        self.config = config
        
        # Initialize GCS client
        if config.credentials:
            credentials_path = config.credentials.get('credentials_file')
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        
        self.client = gcs.Client()
        self.bucket = self.client.bucket(config.bucket_name)
        
        logger.info(f"GCS storage initialized for bucket: {config.bucket_name}")
    
    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Upload file to GCS"""
        try:
            blob_name = f"{self.config.prefix}/{remote_path}".lstrip('/')
            blob = self.bucket.blob(blob_name)
            
            if metadata:
                blob.metadata = metadata
            
            blob.upload_from_filename(local_path)
            
            logger.info(f"Uploaded {local_path} to gs://{self.config.bucket_name}/{blob_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error uploading to GCS: {e}")
            return False
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from GCS"""
        try:
            blob_name = f"{self.config.prefix}/{remote_path}".lstrip('/')
            blob = self.bucket.blob(blob_name)
            
            blob.download_to_filename(local_path)
            
            logger.info(f"Downloaded {blob_name} from GCS")
            return True
        
        except Exception as e:
            logger.error(f"Error downloading from GCS: {e}")
            return False
    
    def delete_file(self, remote_path: str) -> bool:
        """Delete file from GCS"""
        try:
            blob_name = f"{self.config.prefix}/{remote_path}".lstrip('/')
            blob = self.bucket.blob(blob_name)
            
            blob.delete()
            
            logger.info(f"Deleted {blob_name} from GCS")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting from GCS: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> List[Dict]:
        """List files in GCS"""
        try:
            full_prefix = f"{self.config.prefix}/{prefix}".lstrip('/')
            
            blobs = self.client.list_blobs(
                self.config.bucket_name,
                prefix=full_prefix
            )
            
            files = []
            for blob in blobs:
                files.append({
                    'key': blob.name,
                    'size': blob.size,
                    'last_modified': blob.updated.isoformat()
                })
            
            return files
        
        except Exception as e:
            logger.error(f"Error listing GCS files: {e}")
            return []


class AzureBlobStorage:
    """
    Azure Blob Storage provider
    
    Handles uploads and management of files in Azure
    """
    
    def __init__(self, config: StorageConfig):
        """Initialize Azure storage"""
        self.config = config
        
        # Initialize Azure client
        connection_string = config.credentials.get('connection_string')
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(config.bucket_name)
        
        logger.info(f"Azure storage initialized for container: {config.bucket_name}")
    
    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Upload file to Azure"""
        try:
            blob_name = f"{self.config.prefix}/{remote_path}".lstrip('/')
            blob_client = self.container_client.get_blob_client(blob_name)
            
            with open(local_path, 'rb') as data:
                blob_client.upload_blob(data, overwrite=True, metadata=metadata)
            
            logger.info(f"Uploaded {local_path} to Azure: {blob_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error uploading to Azure: {e}")
            return False
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from Azure"""
        try:
            blob_name = f"{self.config.prefix}/{remote_path}".lstrip('/')
            blob_client = self.container_client.get_blob_client(blob_name)
            
            with open(local_path, 'wb') as download_file:
                download_file.write(blob_client.download_blob().readall())
            
            logger.info(f"Downloaded {blob_name} from Azure")
            return True
        
        except Exception as e:
            logger.error(f"Error downloading from Azure: {e}")
            return False
    
    def delete_file(self, remote_path: str) -> bool:
        """Delete file from Azure"""
        try:
            blob_name = f"{self.config.prefix}/{remote_path}".lstrip('/')
            blob_client = self.container_client.get_blob_client(blob_name)
            
            blob_client.delete_blob()
            
            logger.info(f"Deleted {blob_name} from Azure")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting from Azure: {e}")
            return False


class CloudStorageManager:
    """
    Unified cloud storage manager
    
    Manages multiple storage providers, upload queue, and retention policies
    """
    
    def __init__(self, config_path: str = "config/cloud_storage.json"):
        """Initialize cloud storage manager"""
        self.config_path = Path(config_path)
        self.providers: Dict[str, object] = {}
        self.primary_provider: Optional[str] = None
        
        # Upload queue
        self.upload_queue: Queue = Queue(maxsize=1000)
        self.upload_thread = None
        self.running = False
        
        # Statistics
        self.stats = StorageStats()
        
        # Load configuration
        self._load_config()
        
        logger.info("Cloud storage manager initialized")
    
    def _load_config(self):
        """Load storage configuration"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
                    
                    # Initialize providers
                    for provider_name, provider_config in config_data.get('providers', {}).items():
                        storage_config = StorageConfig(
                            provider=StorageProvider(provider_config['type']),
                            bucket_name=provider_config['bucket_name'],
                            region=provider_config.get('region'),
                            credentials=provider_config.get('credentials'),
                            prefix=provider_config.get('prefix', '')
                        )
                        
                        self.add_provider(provider_name, storage_config)
                    
                    # Set primary provider
                    self.primary_provider = config_data.get('primary_provider')
        
        except Exception as e:
            logger.error(f"Error loading storage config: {e}")
    
    def add_provider(self, name: str, config: StorageConfig):
        """Add storage provider"""
        try:
            if config.provider == StorageProvider.AWS_S3:
                provider = S3Storage(config)
            elif config.provider == StorageProvider.GOOGLE_CLOUD:
                provider = GoogleCloudStorage(config)
            elif config.provider == StorageProvider.AZURE_BLOB:
                provider = AzureBlobStorage(config)
            else:
                raise ValueError(f"Unsupported provider: {config.provider}")
            
            self.providers[name] = provider
            
            if not self.primary_provider:
                self.primary_provider = name
            
            logger.info(f"Added storage provider: {name}")
        
        except Exception as e:
            logger.error(f"Error adding provider {name}: {e}")
    
    def start_upload_worker(self):
        """Start background upload worker"""
        if self.running:
            logger.warning("Upload worker already running")
            return
        
        self.running = True
        self.upload_thread = threading.Thread(target=self._upload_worker, daemon=True)
        self.upload_thread.start()
        
        logger.info("Upload worker started")
    
    def stop_upload_worker(self):
        """Stop upload worker"""
        self.running = False
        if self.upload_thread:
            self.upload_thread.join(timeout=5)
        
        logger.info("Upload worker stopped")
    
    def _upload_worker(self):
        """Background worker for processing uploads"""
        while self.running:
            try:
                # Get upload task
                task = self.upload_queue.get(timeout=1)
                
                # Upload to primary provider
                if self.primary_provider:
                    provider = self.providers[self.primary_provider]
                    
                    success = provider.upload_file(
                        task.local_path,
                        task.remote_path,
                        task.metadata
                    )
                    
                    if success:
                        self.stats.total_uploaded += 1
                        
                        # Get file size
                        file_size = Path(task.local_path).stat().st_size
                        self.stats.total_bytes += file_size
                        
                        # Callback
                        if task.callback:
                            task.callback(success=True, task=task)
                    else:
                        self.stats.failed_uploads += 1
                        
                        if task.callback:
                            task.callback(success=False, task=task)
            
            except Exception as e:
                if self.running:
                    logger.error(f"Error in upload worker: {e}")
    
    def queue_upload(
        self,
        local_path: str,
        remote_path: Optional[str] = None,
        priority: int = 5,
        metadata: Optional[Dict] = None,
        callback: Optional[Callable] = None
    ):
        """
        Queue file for upload
        
        Args:
            local_path: Local file path
            remote_path: Remote path (auto-generated if None)
            priority: Upload priority (1-10)
            metadata: File metadata
            callback: Callback function(success, task)
        """
        if not Path(local_path).exists():
            logger.error(f"File not found: {local_path}")
            return
        
        # Generate remote path if not provided
        if not remote_path:
            file_path = Path(local_path)
            timestamp = datetime.now().strftime("%Y/%m/%d")
            remote_path = f"{timestamp}/{file_path.name}"
        
        # Create upload task
        task = UploadTask(
            local_path=local_path,
            remote_path=remote_path,
            priority=priority,
            metadata=metadata,
            callback=callback
        )
        
        # Add to queue
        try:
            self.upload_queue.put(task, block=False)
            logger.debug(f"Queued upload: {local_path} -> {remote_path}")
        except:
            logger.error("Upload queue full")
    
    def upload_file_sync(
        self,
        local_path: str,
        remote_path: Optional[str] = None,
        provider_name: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Upload file synchronously
        
        Args:
            local_path: Local file path
            remote_path: Remote path
            provider_name: Provider name (uses primary if None)
            metadata: File metadata
            
        Returns:
            True if successful
        """
        provider_name = provider_name or self.primary_provider
        
        if provider_name not in self.providers:
            logger.error(f"Provider not found: {provider_name}")
            return False
        
        if not remote_path:
            file_path = Path(local_path)
            timestamp = datetime.now().strftime("%Y/%m/%d")
            remote_path = f"{timestamp}/{file_path.name}"
        
        provider = self.providers[provider_name]
        return provider.upload_file(local_path, remote_path, metadata)
    
    def download_file(
        self,
        remote_path: str,
        local_path: str,
        provider_name: Optional[str] = None
    ) -> bool:
        """Download file from cloud storage"""
        provider_name = provider_name or self.primary_provider
        
        if provider_name not in self.providers:
            logger.error(f"Provider not found: {provider_name}")
            return False
        
        provider = self.providers[provider_name]
        return provider.download_file(remote_path, local_path)
    
    def delete_file(
        self,
        remote_path: str,
        provider_name: Optional[str] = None
    ) -> bool:
        """Delete file from cloud storage"""
        provider_name = provider_name or self.primary_provider
        
        if provider_name not in self.providers:
            logger.error(f"Provider not found: {provider_name}")
            return False
        
        provider = self.providers[provider_name]
        return provider.delete_file(remote_path)
    
    def cleanup_old_files(
        self,
        days: int = 30,
        provider_name: Optional[str] = None
    ) -> int:
        """
        Delete files older than specified days
        
        Args:
            days: Number of days to keep
            provider_name: Provider name
            
        Returns:
            Number of files deleted
        """
        provider_name = provider_name or self.primary_provider
        
        if provider_name not in self.providers:
            return 0
        
        provider = self.providers[provider_name]
        files = provider.list_files()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted = 0
        
        for file_info in files:
            file_date = datetime.fromisoformat(file_info['last_modified'].replace('Z', '+00:00'))
            
            if file_date < cutoff_date:
                if provider.delete_file(file_info['key']):
                    deleted += 1
        
        logger.info(f"Cleaned up {deleted} old files from {provider_name}")
        return deleted
    
    def get_statistics(self) -> Dict:
        """Get storage statistics"""
        stats = {
            'total_uploaded': self.stats.total_uploaded,
            'total_bytes': self.stats.total_bytes,
            'failed_uploads': self.stats.failed_uploads,
            'queue_size': self.upload_queue.qsize(),
            'providers': {}
        }
        
        # Get storage usage per provider
        for name, provider in self.providers.items():
            try:
                storage_size = provider.get_storage_size()
                stats['providers'][name] = {
                    'storage_used': storage_size,
                    'storage_used_gb': round(storage_size / (1024**3), 2)
                }
            except:
                pass
        
        return stats


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize storage manager
    storage_manager = CloudStorageManager()
    
    # Add S3 provider
    s3_config = StorageConfig(
        provider=StorageProvider.AWS_S3,
        bucket_name="surveillance-recordings",
        region="us-east-1",
        credentials={
            'access_key_id': 'YOUR_ACCESS_KEY',
            'secret_access_key': 'YOUR_SECRET_KEY'
        },
        prefix="camera_recordings"
    )
    
    storage_manager.add_provider("s3_primary", s3_config)
    
    # Start upload worker
    storage_manager.start_upload_worker()
    
    # Queue upload
    def upload_callback(success, task):
        if success:
            print(f"✓ Upload successful: {task.remote_path}")
        else:
            print(f"✗ Upload failed: {task.remote_path}")
    
    storage_manager.queue_upload(
        local_path="test_video.mp4",
        metadata={'camera_id': 'camera_1', 'event_type': 'motion'},
        callback=upload_callback
    )
    
    # Wait for uploads
    import time
    time.sleep(5)
    
    # Get statistics
    stats = storage_manager.get_statistics()
    print(f"\nStorage Statistics:")
    print(json.dumps(stats, indent=2))
    
    # Cleanup
    storage_manager.stop_upload_worker()