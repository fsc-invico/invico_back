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

from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    Field,
    field_validator,
    model_validator,
)

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
    pending = "pending"  # 👈 Estado de "Sala de espera" (rol exclusivo)
    eecc = "eecc"  # 👈 Encargado de Estados Contables
    icaro = "icaro"  # 👈 Encargado del sistema ICARO


# -------------------------------------------------
def _coerce_roles(value: object) -> object:
    """Normaliza el campo `roles` al nuevo formato lista.

    Acepta el formato legacy (`"admin"`) y lo convierte en lista
    (`["admin"]`), permitiendo leer documentos de MongoDB y payloads JWT
    anteriores a la migración `scripts/migrate_roles.py`.
    """
    if isinstance(value, Enum):
        return [value.value]
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item.value if isinstance(item, Enum) else item for item in value]
    return value


# Tipo reutilizable: lista de roles con coerción backward-compatible
RolesList = Annotated[list[Role], BeforeValidator(_coerce_roles)]


# -------------------------------------------------
def _validate_roles_combination(value: list[Role]) -> list[Role]:
    """Reglas de negocio sobre la lista de roles enviada en requests."""
    if not value:
        raise ValueError("Debe indicar al menos un rol.")
    if len(set(value)) != len(value):
        raise ValueError("No se permiten roles duplicados.")
    if Role.pending in value and set(value) != {Role.pending}:
        raise ValueError("El rol 'pending' no puede combinarse con otros roles.")
    return value


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
    roles: list[RegisterRole] = [RegisterRole.pending]
    password: str


# -------------------------------------------------
class CreateUser(RegisterUser):
    roles: RolesList = [Role.user]
    _not_empty = field_validator("username", "password", mode="after")(
        validate_not_empty
    )
    _validate_roles = field_validator("roles", mode="after")(
        _validate_roles_combination
    )


# -------------------------------------------------
class UpdateUserRole(BaseModel):
    roles: RolesList = [Role.user]
    _validate_roles = field_validator("roles", mode="after")(
        _validate_roles_combination
    )


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
    roles: RolesList

    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_role(cls, data: object) -> object:
        """Mapea el campo legacy `role` (string) al nuevo `roles` (lista).

        Permite validar documentos de MongoDB anteriores a la migración
        `scripts/migrate_roles.py` sin errores de validación.
        """
        if isinstance(data, dict) and "roles" not in data and "role" in data:
            data = {**data, "roles": data["role"]}
        return data


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
    roles: RolesList
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
