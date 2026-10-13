"""Private blob storage for uploaded documents.

Local/test environments use the Azurite emulator with its public development
account. The protocol keeps the production managed-identity wiring (M7) a
drop-in replacement and lets tests inject an in-memory backend.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.config import get_settings

CONTAINER = "user-documents"
_LOCAL_AZURITE_ACCOUNT_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
)


class StorageError(RuntimeError):
    pass


class StorageNotFound(StorageError):
    pass


class DocumentStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class AzuriteDocumentStorage:
    """Documents container on the configured blob endpoint (Azurite locally)."""

    def __init__(self, account_url: str, credential: str) -> None:
        self._client = BlobServiceClient(
            account_url=account_url,
            credential=credential,
            api_version="2023-11-03",
            connection_timeout=5,
            read_timeout=30,
            retry_total=1,
        )
        container = self._client.get_container_client(CONTAINER)
        try:
            container.create_container()
        except AzureError:
            pass
        self._container = container

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._container.upload_blob(
                key,
                data,
                overwrite=False,
                content_settings=ContentSettings(content_type=content_type),
            )
        except AzureError as error:
            raise StorageError("document upload failed") from error

    def get(self, key: str) -> bytes:
        try:
            return self._container.download_blob(key).readall()
        except ResourceNotFoundError as error:
            raise StorageNotFound("document blob is missing") from error
        except AzureError as error:
            raise StorageError("document download failed") from error

    def delete(self, key: str) -> None:
        try:
            self._container.delete_blob(key)
        except ResourceNotFoundError:
            return
        except AzureError as error:
            raise StorageError("document deletion failed") from error


class InMemoryDocumentStorage:
    """Deterministic backend for tests and local contract checks."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        if key in self.objects:
            raise StorageError("document blob already exists")
        self.objects[key] = (bytes(data), content_type)

    def get(self, key: str) -> bytes:
        try:
            return self.objects[key][0]
        except KeyError as error:
            raise StorageNotFound("document blob is missing") from error

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@lru_cache(maxsize=1)
def document_storage() -> DocumentStorage:
    settings = get_settings()
    return AzuriteDocumentStorage(settings.blob_endpoint_url, _LOCAL_AZURITE_ACCOUNT_KEY)
