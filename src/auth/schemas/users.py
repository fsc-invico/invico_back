__all__ = [
    "CreateUser",
    "UpdateUserRole",
    "LoginUser",
    "RegisterUser",
    "UserRegistrationForm",
    "PublicStoredUser",
    "PrivateStoredUser",
    "PrivateUser",
    "Role",
    "UserFullFilter",
    "ExternalCredentialIn",
    "ExternalCredential",
]

from enum import Enum
from typing import Annotated, Optional

from pydantic import AliasChoices, BaseModel, BeforeValidator, Field, field_validator

from ...utils import BaseFilterParams, CamelModel, validate_not_empty

# Creamos un tipo que convierte automáticamente ObjectId a str
PyObjectIdStr = Annotated[str, BeforeValidator(str)]


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


# Este es el que ve el usuario en Swagger/Streamlit
# -------------------------------------------------
class UserRegistrationForm(BaseUser):
    password: str
    _not_empty = field_validator("username", "password", mode="after")(
        validate_not_empty
    )


# Este es el que usas internamente para el Service/Repo (ya lo tienes)
# -------------------------------------------------
class RegisterUser(BaseUser):
    role: RegisterRole = RegisterRole.pending
    password: str


# -------------------------------------------------
class CreateUser(RegisterUser):
    role: Role = Role.user
    _not_empty = field_validator("username", "password", mode="after")(
        validate_not_empty
    )


# -------------------------------------------------
class UpdateUserRole(BaseModel):
    role: Role = Role.user


# -------------------------------------------------
class LoginUser(BaseUser):
    password: str


# -------------------------------------------------
# 1. Base compartida para TODO usuario que ya está en la DB
# -------------------------------------------------
class BaseStoredUser(BaseModel):
    # Cambiamos a str para evitar líos con el openapi.json
    id: PyObjectIdStr = Field(validation_alias=AliasChoices("_id", "id"))
    username: str
    role: Role

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# -------------------------------------------------
# 2. El que usas para Login (necesita el hash)
# -------------------------------------------------
class PrivateStoredUser(BaseStoredUser):
    hash_password: str


# -------------------------------------------------
# 3. El que usas para GET (Seguro, sin hash)
# -------------------------------------------------
class PublicStoredUser(BaseStoredUser):
    # Ya hereda id y role de BaseStoredUser
    # Aquí puedes agregar campos extra como deactivated_at
    pass


# -------------------------------------------------
# 4. Ajuste en PrivateUser (si lo usas en el repositorio)
# -------------------------------------------------
class PrivateUser(BaseUser):  # 👈 CAMBIO: Heredar de BaseUser (no sé si es correcto)
    role: Role
    hash_password: str 
    _not_empty = field_validator("username", "hash_password", mode="after")(
        validate_not_empty
    )


# Este se usa para la tabla (UI)
# -------------------------------------------------
class UserFullFilter(BaseFilterParams):
    username: Optional[str] = None


# -------------------------------------------------
class ExternalCredentialIn(CamelModel):
    system_name: str  # Ej: "SIIF", "INVICO"
    external_username: str  # El usuario del sistema de terceros
    external_password: str  # El password que vamos a cifrar


# -------------------------------------------------
class ExternalCredential(CamelModel):
    user_id: str  # El ID del usuario en tu sistema (ObjectId como str)
    system_name: str  # Ej: "SIIF", "INVICO"
    external_username: str  # El usuario del sistema de terceros
    encrypted_pass: str


# -------------------------------------------------
class ExternalStoredCredential(ExternalCredential):
    id: PyObjectIdStr = Field(validation_alias=AliasChoices("_id", "id"))
