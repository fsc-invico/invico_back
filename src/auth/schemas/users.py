__all__ = [
    "CreateUser",
    "LoginUser",
    "RegisterUser",
    "PublicStoredUser",
    "PrivateStoredUser",
    "PrivateUser",
]

from datetime import datetime
from enum import Enum

from pydantic import AliasChoices, BaseModel, Field, field_validator

from ...utils import PyObjectId, validate_not_empty


# -------------------------------------------------
class RegisterRole(str, Enum):
    pending = "pending"


# -------------------------------------------------
class Role(str, Enum):
    admin = "admin"
    user = "user"
    pending = "pending"  # 👈 El nuevo rol de "Sala de espera"


# -------------------------------------------------
class BaseUser(BaseModel):
    username: str


# -------------------------------------------------
class RegisterUser(BaseUser):
    role: RegisterRole = RegisterRole.pending
    password: str
    _not_empty = field_validator("username", "password", mode="after")(
        validate_not_empty
    )


# -------------------------------------------------
class CreateUser(RegisterUser):
    role: Role = Role.user
    _not_empty = field_validator("username", "password", mode="after")(
        validate_not_empty
    )


# -------------------------------------------------
class LoginUser(BaseUser):
    password: str


# -------------------------------------------------
class PrivateUser(BaseUser):
    role: Role
    hash_password: str
    _not_empty = field_validator("username", "hash_password", mode="after")(
        validate_not_empty
    )


# -------------------------------------------------
# 1. Base compartida (sin datos sensibles)
# -------------------------------------------------
class BaseStoredUser(BaseUser):
    id: PyObjectId = Field(validation_alias=AliasChoices("_id", "id"))
    role: Role
    deactivated_at: datetime | None = Field(default=None)


# -------------------------------------------------
# 2. El que usas para el endpoint /authenticated_user y otros GET
# -------------------------------------------------
class PublicStoredUser(BaseStoredUser):
    # Ya no hereda de PrivateUser, por lo tanto NO tiene hash_password
    pass


# -------------------------------------------------
# 3. El que usas internamente en Authentication (Login)
# -------------------------------------------------
class PrivateStoredUser(BaseStoredUser):
    hash_password: str
