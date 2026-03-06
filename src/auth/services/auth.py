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
        self.user_id = payload.get("id")
        self.username = payload.get("username")
        self.role = payload.get("role")

    # # -------------------------------------------------
    # @property
    # def is_admin(self) -> bool:
    #     return self.role == "admin"

    # # -------------------------------------------------
    # @property
    # def is_user(self) -> bool:
    #     return self.role == "user"

    # -------------------------------------------------
    def is_admin_or_raise(self):
        if self.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requieren permisos de administrador",
            )

    # -------------------------------------------------
    def is_admin_or_user_or_raise(self):
        # 1. Si es admin o usuario validado, puede entrar
        if self.role in ["admin", "user"]:
            return

        # 2. Si es 'pending', bloqueamos el acceso
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Su cuenta requiere aprobación para visualizar reportes financieros.",
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
            "role": "admin",
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
