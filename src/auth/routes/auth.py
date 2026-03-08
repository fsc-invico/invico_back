__all__ = ["auth_router"]

from typing import Annotated

from fastapi import APIRouter, Form, Response

from ..schemas import LoginUser, RegisterUser, UserRegistrationForm
from ..services import (
    AuthenticationDependency,
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
@auth_router.post("/logout", include_in_schema=False)
def logout():
    pass
