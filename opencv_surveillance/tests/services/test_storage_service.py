# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for cloud storage service module
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
import asyncio
from datetime import datetime, timedelta

from backend.services.storage_service import (
    CloudStorageService,
    get_storage_service,
    initialize_storage_service,
)


class TestCloudStorageServiceInitialization:
    """Test CloudStorageService initialization"""

    @patch('boto3.client')
    def test_init_s3_with_credentials(self, mock_boto3_client):
        """Test S3 initialization with provided credentials"""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        service = CloudStorageService(
            provider="s3",
            bucket_name="test-bucket",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-west-2"
        )

        assert service.provider == "s3"
        assert service.bucket_name == "test-bucket"
        assert service.client == mock_client
        mock_boto3_client.assert_called_once_with(
            "s3",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-west-2"
        )

    @patch('boto3.client')
    @patch.dict('os.environ', {
        'AWS_ACCESS_KEY_ID': 'env-key',
        'AWS_SECRET_ACCESS_KEY': 'env-secret'
    })
    def test_init_s3_from_env(self, mock_boto3_client):
        """Test S3 initialization from environment variables"""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        service = CloudStorageService(
            provider="s3",
            bucket_name="test-bucket"
        )

        # Should use environment variables
        mock_boto3_client.assert_called_once()
        call_kwargs = mock_boto3_client.call_args[1]
        assert call_kwargs["aws_access_key_id"] == "env-key"
        assert call_kwargs["aws_secret_access_key"] == "env-secret"

    @patch('boto3.client')
    def test_init_s3_error(self, mock_boto3_client):
        """Test S3 initialization error handling"""
        mock_boto3_client.side_effect = Exception("AWS connection error")

        with pytest.raises(Exception) as exc_info:
            CloudStorageService(
                provider="s3",
                bucket_name="test-bucket",
                aws_access_key_id="test-key"
            )

        assert "AWS connection error" in str(exc_info.value)

    @patch('google.cloud.storage.Client')
    def test_init_gcs_with_credentials(self, mock_gcs_client):
        """Test GCS initialization with credentials path"""
        # Mock the google.cloud.storage.Client
        mock_client = MagicMock()
        mock_gcs_client.return_value = mock_client

        with patch('os.environ', {}):
            service = CloudStorageService(
                provider="gcs",
                bucket_name="test-bucket",
                credentials_path="/path/to/creds.json",
                project_id="test-project"
            )

        assert service.provider == "gcs"
        assert service.bucket_name == "test-bucket"
        assert service.client == mock_client
        mock_gcs_client.assert_called_once_with(project="test-project")

    @patch('azure.storage.blob.BlobServiceClient.from_connection_string')
    @patch.dict('os.environ', {'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;'})
    def test_init_azure_from_env(self, mock_from_connection_string):
        """Test Azure initialization from environment variable"""
        mock_client = MagicMock()
        mock_from_connection_string.return_value = mock_client

        service = CloudStorageService(
            provider="azure",
            bucket_name="test-container"
        )

        assert service.provider == "azure"
        assert service.bucket_name == "test-container"
        assert service.client == mock_client
        mock_from_connection_string.assert_called_once_with(
            'DefaultEndpointsProtocol=https;'
        )

    @patch('azure.storage.blob.BlobServiceClient.from_connection_string')
    def test_init_azure_with_connection_string(self, mock_from_connection_string):
        """Test Azure initialization with connection string"""
        mock_client = MagicMock()
        mock_from_connection_string.return_value = mock_client

        service = CloudStorageService(
            provider="azure",
            bucket_name="test-container",
            connection_string="custom-connection-string"
        )

        mock_from_connection_string.assert_called_once_with(
            "custom-connection-string"
        )

    def test_init_unsupported_provider(self):
        """Test initialization with unsupported provider"""
        with pytest.raises(ValueError) as exc_info:
            CloudStorageService(
                provider="dropbox",
                bucket_name="test-bucket"
            )

        assert "Unsupported provider: dropbox" in str(exc_info.value)


class TestS3Operations:
    """Test S3 upload, delete, and URL generation"""

    @pytest.fixture
    def s3_service(self):
        """Create S3 service with mocked boto3"""
        with patch('boto3.client') as mock_boto3_client:
            mock_client = MagicMock()
            mock_boto3_client.return_value = mock_client

            service = CloudStorageService(
                provider="s3",
                bucket_name="test-bucket",
                aws_access_key_id="test-key"
            )

            yield service

    @pytest.mark.asyncio
    async def test_upload_s3_success(self, s3_service):
        """Test successful S3 upload"""
        s3_service.client.upload_file = MagicMock()

        result = await s3_service.upload_file(
            local_path="/tmp/test.mp4",
            remote_path="recordings/test.mp4",
            metadata={"camera": "cam1", "duration": "60"}
        )

        assert result is True
        s3_service.client.upload_file.assert_called_once()
        call_args = s3_service.client.upload_file.call_args
        assert call_args[0] == ("/tmp/test.mp4", "test-bucket", "recordings/test.mp4")
        assert "Metadata" in call_args[1]["ExtraArgs"]

    @pytest.mark.asyncio
    async def test_upload_s3_without_metadata(self, s3_service):
        """Test S3 upload without metadata"""
        s3_service.client.upload_file = MagicMock()

        result = await s3_service.upload_file(
            local_path="/tmp/test.mp4",
            remote_path="recordings/test.mp4"
        )

        assert result is True
        s3_service.client.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_s3_error(self, s3_service):
        """Test S3 upload error handling"""
        s3_service.client.upload_file.side_effect = Exception("Upload failed")

        result = await s3_service.upload_file(
            local_path="/tmp/test.mp4",
            remote_path="recordings/test.mp4"
        )

        assert result is False

    def test_generate_presigned_url_s3(self, s3_service):
        """Test S3 presigned URL generation"""
        s3_service.client.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-bucket/file.mp4?signature=..."

        url = s3_service.generate_presigned_url(
            remote_path="recordings/test.mp4",
            expiration=7200
        )

        assert url.startswith("https://s3.amazonaws.com")
        s3_service.client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "test-bucket", "Key": "recordings/test.mp4"},
            ExpiresIn=7200
        )

    def test_generate_presigned_url_s3_error(self, s3_service):
        """Test S3 presigned URL generation error"""
        s3_service.client.generate_presigned_url.side_effect = Exception("Invalid credentials")

        url = s3_service.generate_presigned_url(
            remote_path="recordings/test.mp4"
        )

        assert url is None

    @pytest.mark.asyncio
    async def test_delete_s3_success(self, s3_service):
        """Test successful S3 file deletion"""
        s3_service.client.delete_object = MagicMock()

        result = await s3_service.delete_file("recordings/test.mp4")

        assert result is True
        s3_service.client.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_s3_error(self, s3_service):
        """Test S3 deletion error handling"""
        s3_service.client.delete_object.side_effect = Exception("Delete failed")

        result = await s3_service.delete_file("recordings/test.mp4")

        assert result is False


class TestGCSOperations:
    """Test Google Cloud Storage operations"""

    @pytest.fixture
    def gcs_service(self):
        """Create GCS service with mocked google.cloud.storage"""
        with patch('google.cloud.storage.Client') as mock_gcs_client:
            mock_client = MagicMock()
            mock_gcs_client.return_value = mock_client

            service = CloudStorageService(
                provider="gcs",
                bucket_name="test-bucket",
                project_id="test-project"
            )

            yield service

    @pytest.mark.asyncio
    async def test_upload_gcs_success(self, gcs_service):
        """Test successful GCS upload"""
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        gcs_service.client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        result = await gcs_service.upload_file(
            local_path="/tmp/test.mp4",
            remote_path="recordings/test.mp4",
            metadata={"camera": "cam1"}
        )

        assert result is True
        gcs_service.client.bucket.assert_called_once_with("test-bucket")
        mock_bucket.blob.assert_called_once_with("recordings/test.mp4")
        assert mock_blob.metadata == {"camera": "cam1"}
        mock_blob.upload_from_filename.assert_called_once_with("/tmp/test.mp4")

    @pytest.mark.asyncio
    async def test_upload_gcs_error(self, gcs_service):
        """Test GCS upload error handling"""
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        gcs_service.client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.upload_from_filename.side_effect = Exception("Upload failed")

        result = await gcs_service.upload_file(
            local_path="/tmp/test.mp4",
            remote_path="recordings/test.mp4"
        )

        assert result is False

    def test_generate_presigned_url_gcs(self, gcs_service):
        """Test GCS signed URL generation"""
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        gcs_service.client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/test-bucket/file.mp4?signature=..."

        url = gcs_service.generate_presigned_url(
            remote_path="recordings/test.mp4",
            expiration=3600
        )

        assert url.startswith("https://storage.googleapis.com")
        mock_blob.generate_signed_url.assert_called_once()
        call_kwargs = mock_blob.generate_signed_url.call_args[1]
        assert "expiration" in call_kwargs

    @pytest.mark.asyncio
    async def test_delete_gcs_success(self, gcs_service):
        """Test successful GCS file deletion"""
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        gcs_service.client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        result = await gcs_service.delete_file("recordings/test.mp4")

        assert result is True
        mock_blob.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_gcs_error(self, gcs_service):
        """Test GCS deletion error handling"""
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        gcs_service.client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.delete.side_effect = Exception("Delete failed")

        result = await gcs_service.delete_file("recordings/test.mp4")

        assert result is False


class TestAzureOperations:
    """Test Azure Blob Storage operations"""

    @pytest.fixture
    def azure_service(self):
        """Create Azure service with mocked BlobServiceClient"""
        with patch('azure.storage.blob.BlobServiceClient.from_connection_string') as mock_from_conn_string:
            mock_client = MagicMock()
            mock_from_conn_string.return_value = mock_client

            service = CloudStorageService(
                provider="azure",
                bucket_name="test-container",
                connection_string="test-connection-string"
            )

            yield service

    @pytest.mark.asyncio
    async def test_upload_azure_success(self, azure_service):
        """Test successful Azure upload"""
        mock_blob_client = MagicMock()
        azure_service.client.get_blob_client.return_value = mock_blob_client

        with patch('builtins.open', mock_open(read_data=b"video data")):
            result = await azure_service.upload_file(
                local_path="/tmp/test.mp4",
                remote_path="recordings/test.mp4",
                metadata={"camera": "cam1"}
            )

        assert result is True
        azure_service.client.get_blob_client.assert_called_once_with(
            container="test-container",
            blob="recordings/test.mp4"
        )
        mock_blob_client.upload_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_azure_error(self, azure_service):
        """Test Azure upload error handling"""
        mock_blob_client = MagicMock()
        azure_service.client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.upload_blob.side_effect = Exception("Upload failed")

        with patch('builtins.open', mock_open(read_data=b"video data")):
            result = await azure_service.upload_file(
                local_path="/tmp/test.mp4",
                remote_path="recordings/test.mp4"
            )

        assert result is False

    @patch('azure.storage.blob.generate_blob_sas')
    @patch('azure.storage.blob.BlobSasPermissions')
    def test_generate_presigned_url_azure(self, mock_sas_perms, mock_gen_sas, azure_service):
        """Test Azure SAS URL generation"""
        # Mock Azure SAS token generation
        mock_gen_sas.return_value = "sas_token_abc123"
        azure_service.client.account_name = "testaccount"
        azure_service.client.credential = MagicMock()
        azure_service.client.credential.account_key = "test-key"

        url = azure_service.generate_presigned_url(
            remote_path="recordings/test.mp4",
            expiration=3600
        )

        assert url is not None
        assert "testaccount.blob.core.windows.net" in url
        assert "sas_token_abc123" in url
        mock_gen_sas.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_azure_success(self, azure_service):
        """Test successful Azure file deletion"""
        mock_blob_client = MagicMock()
        azure_service.client.get_blob_client.return_value = mock_blob_client

        result = await azure_service.delete_file("recordings/test.mp4")

        assert result is True
        mock_blob_client.delete_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_azure_error(self, azure_service):
        """Test Azure deletion error handling"""
        mock_blob_client = MagicMock()
        azure_service.client.get_blob_client.return_value = mock_blob_client
        mock_blob_client.delete_blob.side_effect = Exception("Delete failed")

        result = await azure_service.delete_file("recordings/test.mp4")

        assert result is False


class TestGlobalFunctions:
    """Test global singleton functions"""

    def test_get_storage_service_none(self):
        """Test get_storage_service returns None when not initialized"""
        # Reset global variable
        import backend.services.storage_service as sss
        sss._storage_service = None

        service = get_storage_service()
        assert service is None

    @patch('boto3.client')
    def test_initialize_storage_service(self, mock_boto3_client):
        """Test initialize_storage_service creates and returns service"""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        service = initialize_storage_service(
            provider="s3",
            bucket_name="test-bucket",
            aws_access_key_id="test-key"
        )

        assert service is not None
        assert service.provider == "s3"
        assert service.bucket_name == "test-bucket"

        # Verify it's stored globally
        assert get_storage_service() == service

    @patch('boto3.client')
    def test_initialize_storage_service_replaces_existing(self, mock_boto3_client):
        """Test initialize_storage_service replaces existing instance"""
        mock_client = MagicMock()
        mock_boto3_client.return_value = mock_client

        # Initialize first service
        service1 = initialize_storage_service(
            provider="s3",
            bucket_name="bucket1",
            aws_access_key_id="key1"
        )

        # Initialize second service (should replace)
        service2 = initialize_storage_service(
            provider="s3",
            bucket_name="bucket2",
            aws_access_key_id="key2"
        )

        assert service1 != service2
        assert get_storage_service() == service2
        assert get_storage_service().bucket_name == "bucket2"
