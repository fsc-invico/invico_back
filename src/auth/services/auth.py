# src/auth/service.py

__all__ = [
    "Authentication",
    "AuthenticationDependency",
    "AuthorizationDependency",
]


from datetime import timedelta
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Response, Security, status
from fastapi_jwt import JwtAccessBearer, JwtAuthorizationCredentials
from passlib.context import CryptContext

from ...config import settings  # Asegúrate que JWT_SECRET esté aquí
from ..schemas import LoginUser, PublicStoredUser

token_expiration_time = timedelta(days=1)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuración única de JWT (Obligatoria)
access_security = JwtAccessBearer(
    secret_key=settings.JWT_SECRET,
    auto_error=True,  # Lanza 401 automáticamente si no hay token válido
)

access_security_optional = JwtAccessBearer(
    secret_key=settings.JWT_SECRET,
    auto_error=False,  # No lanza error automáticamente, lo manejamos manualmente en get_authorization
)

# 1. El alias de tipo (para Swagger y FastAPI)
AuthCredentials = Annotated[JwtAuthorizationCredentials, Security(access_security)]


# -------------------------------------------------
class Authentication:
    @staticmethod
    # -------------------------------------------------
    def verify_password(plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    # -------------------------------------------------
    def get_password_hash(password):
        return pwd_context.hash(password)

    # -------------------------------------------------
    def login_and_set_access_token(
        self, db_user: dict | None, user: LoginUser, response: Response
    ):
        if not db_user or not self.verify_password(
            user.password, db_user.get("hash_password")
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas",
            )

        # El 'subject' es lo que viaja en el token (el payload)
        # userdata = {
        #     "id": str(db_user["_id"]),
        #     "username": db_user["username"],
        #     "role": db_user.get("role", "user"),
        # }
        userdata = PublicStoredUser.model_validate(db_user).model_dump()

        access_token = access_security.create_access_token(
            subject=userdata, expires_delta=token_expiration_time
        )
        access_security.set_access_cookie(response, access_token)
        return {"access_token": access_token}


# -------------------------------------------------
class Authorization:
    def __init__(
        self,
        credentials: AuthCredentials,  # type: ignore
    ):
        # def __init__(self, credentials: JwtAuthorizationCredentials):
        # Aquí credentials nunca será None por el auto_error=True
        payload = credentials.subject
        self.user_id: str | None = payload.get("id")
        self.username: str | None = payload.get("username")
        # Lista de roles del usuario (soporta el payload legacy con "role")
        self.roles: list[str] = self._extract_roles(payload)

    # -------------------------------------------------
    @staticmethod
    def _extract_roles(payload: dict) -> list[str]:
        """Normaliza los roles del payload JWT al nuevo formato lista.

        Los tokens emitidos antes del cambio traen `role: "admin"` (string);
        los nuevos traen `roles: ["admin", ...]`. Soportamos ambos durante
        la vigencia de los tokens (1 día).
        """
        roles = payload.get("roles")
        if isinstance(roles, list) and roles:
            return [str(role) for role in roles]
        legacy_role = payload.get("role")
        if isinstance(legacy_role, str) and legacy_role:
            return [legacy_role]
        return []

    # -------------------------------------------------
    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

    # -------------------------------------------------
    @property
    def is_user(self) -> bool:
        return "user" in self.roles

    # -------------------------------------------------
    def has_any_role(self, *roles: str) -> bool:
        return any(role in self.roles for role in roles)

    # -------------------------------------------------
    def is_admin_or_raise(self) -> None:
        if not self.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requieren permisos de administrador",
            )

    # -------------------------------------------------
    def is_admin_or_user_or_raise(self) -> None:
        # 1. Si es admin o usuario validado, puede entrar
        if self.has_any_role("admin", "user"):
            return

        # 2. Si es 'pending' (u otro rol sin permisos), bloqueamos el acceso
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Su cuenta requiere aprobación para visualizar reportes financieros.",
        )

    # -------------------------------------------------
    def require_any_role(self, *roles: str, detail: str | None = None) -> None:
        """Autorización genérica para roles específicos (eecc, icaro, etc.)."""
        if not self.has_any_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail
                or (
                    "Acceso denegado. Se requiere uno de los siguientes roles: "
                    f"{', '.join(roles)}."
                ),
            )


# --- DEPENDENCIAS PARA TUS RUTAS ---

# 1. Mantenemos Authentication simple
AuthenticationDependency = Annotated[Authentication, Depends()]


# 2. El "Puente": Esta función es la que realmente sabe extraer el JWT
# def get_authorization(
#     credentials: AuthCredentials,  # type: ignore
# ) -> Authorization:
#     return Authorization(credentials)
def get_authorization(
    # Cambiamos Security por un Depends manual para poder hacerlo opcional
    credentials: Annotated[
        Optional[JwtAuthorizationCredentials], Security(access_security_optional)
    ] = None,
) -> Authorization:

    # 💡 BYPASS DE DESARROLLO
    # Si la configuración lo permite y no hay credenciales, inyectamos un Admin falso
    if settings.BYPASS_AUTH and not credentials:
        # Creamos un objeto Authorization "de mentira" para desarrollo
        # Mockeamos lo que vendría en el JwtAuthorizationCredentials
        from unittest.mock import MagicMock

        mock_credentials = MagicMock()
        mock_credentials.subject = {
            "id": "dev_id",
            "username": "dev_admin",
            "roles": ["admin"],
        }
        return Authorization(mock_credentials)

    # Si no hay bypass y no hay token, JwtAccessBearer(auto_error=True)
    # ya debería haber lanzado el error. Si usas el optional, lánzalo tú:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return Authorization(credentials)


# 3. La dependencia que inyectarás en el RouterFactory
# Al usar Depends(get_authorization), FastAPI ejecutará la validación JWT
# antes de entregarte el objeto Authorization listo para usar.
AuthorizationDependency = Annotated[Authorization, Depends(get_authorization)]
