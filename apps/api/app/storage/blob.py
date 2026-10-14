"""Private blob storage for uploaded documents and export artifacts.

Local/test environments use the Azurite emulator with its public development
account; deployed environments authenticate with the App Service managed
identity (the Storage Blob Data Contributor role in the deployment plan).
Tests can inject the in-memory backend.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from azure.core.credentials import AccessToken, TokenCredential
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, ContentSettings

from app.config import get_settings
from app.security.managed_identity import ManagedIdentityError, managed_identity_token

CONTAINER = "user-documents"
_LOCAL_AZURITE_ACCOUNT_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
)


class StorageError(RuntimeError):
    pass


class StorageNotFound(StorageError):
    pass


class _ManagedIdentityCredential:
    """TokenCredential adapter backed by the App Service IMDS endpoint."""

    def __init__(self, timeout: float = 5.0) -> None:
        self._timeout = timeout

    def get_token(self, *scopes: str, **_: object) -> AccessToken:
        scope = scopes[0] if scopes else "https://storage.azure.net/.default"
        try:
            token, expires_on = managed_identity_token(
                scope.removesuffix("/.default"), self._timeout
            )
        except ManagedIdentityError as error:
            raise StorageError("managed identity token unavailable") from error
        return AccessToken(token, expires_on)


class DocumentStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class BlobDocumentStorage:
    """Documents container on the configured blob endpoint.

    *credential* is the Azurite development key locally or a managed-identity
    token credential in deployed environments.
    """

    def __init__(self, account_url: str, credential: str | TokenCredential) -> None:
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
    credential: str | TokenCredential = (
        _LOCAL_AZURITE_ACCOUNT_KEY
        if settings.app_env in {"local", "test"}
        else _ManagedIdentityCredential()
    )
    return BlobDocumentStorage(settings.blob_endpoint_url, credential)
