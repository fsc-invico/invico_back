__all__ = ["users_router"]

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import (
    CreateUser,
    ExternalCredentialIn,
    PublicStoredUser,
    Role,
    UpdateUserRole,
    UserFullFilter,
)
from ..services import (
    AuthorizationDependency,
    UsersServiceDependency,
)

users_router = APIRouter(prefix="/users", tags=["Users"])


# -------------------------------------------------
@users_router.post("/")
async def create_user(
    user: CreateUser,
    users: UsersServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_raise()
    inserted_id = await users.create_one(user)
    return {"result message": f"User created with id: {inserted_id}"}


# -------------------------------------------------
@users_router.get("/", response_model=List[PublicStoredUser])
async def get_all_users(
    users: UsersServiceDependency,
    security: AuthorizationDependency,
    params: Annotated[UserFullFilter, Depends()],
):
    security.is_admin_or_raise()
    return await users.get_all(params)


# -------------------------------------------------
@users_router.patch("/{user_id}/role")
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
@users_router.patch("/{user_id}/approve")
async def approve_pending_user(
    user_id: str,
    security: AuthorizationDependency,  # 🛡️ Tu dependencia de seguridad
    users_service: UsersServiceDependency,
):
    # 1. Verificación de seguridad estricta
    security.is_admin_or_raise()  # Solo los admins pueden aprobar usuarios

    # 2. Convertimos el string de la URL a ObjectId
    from bson import ObjectId

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="ID de usuario inválido")

    # 3. Llamada al servicio
    return await users_service.approve_user(user_id=ObjectId(user_id))


# -------------------------------------------------
@users_router.get("/me")
async def read_current_user(
    security: AuthorizationDependency,
    users: UsersServiceDependency,
):
    return await users.get_one(id=str(security.user_id))


# -------------------------------------------------
@users_router.post("/me/credentials")
async def save_external_credential(
    data: ExternalCredentialIn,
    security: AuthorizationDependency,
    users_service: UsersServiceDependency,
):
    # Usamos el ID del usuario que viene del Token de seguridad
    user_id = security.user_id

    # Llamamos al servicio para cifrar y guardar
    return await users_service.add_external_credential(user_id=str(user_id), data=data)


# -------------------------------------------------
@users_router.get("/me/credentials")
async def list_my_credentials(
    security: AuthorizationDependency, users_service: UsersServiceDependency
):
    """Lista qué sistemas tiene configurados el usuario actual"""
    return await users_service.get_all_user_credentials(user_id=str(security.user_id))


# ------------------------------------------------
@users_router.delete("/me/credentials/{system_name}")
async def delete_my_credential(
    system_name: str,
    security: AuthorizationDependency,
    users_service: UsersServiceDependency,
):
    """Elimina la configuración de un sistema específico para el usuario actual"""
    return await users_service.delete_user_credential(
        user_id=str(security.user_id), system_name=system_name
    )


# -------------------------------------------------
@users_router.get("/roles")
async def list_roles():
    roles_list = [item.value for item in Role]
    return roles_list


# # -------------------------------------------------
# @users_router.get("/{id}", response_model=PublicStoredUser)
# async def get_one_user(id: ObjectId, users: UsersServiceDependency):
#     return await users.get_one(id=id)


# # -------------------------------------------------
# @users_router.put("/{id}")
# async def update_user(
#     id: ObjectId,
#     user: PublicStoredUser,
#     users: UsersServiceDependency,
#     security: AuthorizationDependency,
# ):

#     security.is_admin_or_raise()
#     return await users.update_one(id=id, user=user, is_admin=security.is_admin)


# # -------------------------------------------------
# @users_router.delete("/delete_hard/{id}")
# async def delete_user_hard(
#     id: ObjectId,
#     users: UsersServiceDependency,
#     security: AuthorizationDependency,
# ):
#     security.is_admin_or_raise()
#     return await users.delete_one_hard(id)
