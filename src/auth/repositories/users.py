__all__ = [
    "UsersRepository",
    "UsersRepositoryDependency",
    "CredentialsRepository",
    "CredentialsRepositoryDependency",
]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ExternalCredential, PrivateUser


class UsersRepository(BaseRepository[PrivateUser]):
    collection_name = "users"
    model = PrivateUser


UsersRepositoryDependency = Annotated[UsersRepository, Depends()]


class CredentialsRepository(BaseRepository[ExternalCredential]):
    collection_name = "external_credentials"
    model = ExternalCredential


CredentialsRepositoryDependency = Annotated[CredentialsRepository, Depends()]
