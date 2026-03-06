__all__ = ["auth_router"]

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Response

from ..schemas import LoginUser, RegisterUser, UpdateUserRole, UserRegistrationForm
from ..services import (
    AuthenticationDependency,
    AuthorizationDependency,
    UsersServiceDependency,
)

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


# -------------------------------------------------
@auth_router.post("/login")
async def login_with_cookie(
    user: Annotated[LoginUser, Form()],
    response: Response,
    users: UsersServiceDependency,
    auth: AuthenticationDependency,
):
    db_user = await users.get_one(username=user.username, with_password=True)
    return auth.login_and_set_access_token(
        user=user, db_user=db_user, response=response
    )


# -------------------------------------------------
@auth_router.post("/register")
async def register(
    form_data: Annotated[UserRegistrationForm, Form()],
    users: UsersServiceDependency,
):
    # Convertimos los datos del formulario al esquema completo de registro
    # El campo 'role' se llenará automáticamente con RegisterRole.pending
    user_internal = RegisterUser(
        username=form_data.username, password=form_data.password
    )

    inserted_id = await users.create_one(user_internal)
    return {"result message": f"User created with id: {inserted_id}"}


# -------------------------------------------------
@auth_router.get("/authenticated_user")
async def read_current_user(
    security: AuthorizationDependency,
    users: UsersServiceDependency,
):
    return await users.get_one(id=security.user_id)


# -------------------------------------------------
@auth_router.patch("/users/{user_id}/role")
async def change_user_role(
    user_id: str,
    data: UpdateUserRole,
    security: AuthorizationDependency,
    users_service: UsersServiceDependency,
):
    security.is_admin_or_raise()  # Solo los admins pueden cambiar roles

    # Convertimos el string de la URL a ObjectId
    from bson import ObjectId

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="ID de usuario inválido")

    return await users_service.update_role(
        user_id=ObjectId(user_id), new_role=data.role
    )


# -------------------------------------------------
@auth_router.post("/logout", include_in_schema=False)
def logout():
    pass
