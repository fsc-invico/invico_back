__all__ = ["users_router"]

from typing import Annotated, List

from bson import ObjectId
from fastapi import APIRouter, Depends

from ..schemas import CreateUser, PublicStoredUser, Role, UserFullFilter
from ..services import (
    AuthorizationDependency,
    UsersServiceDependency,
)

users_router = APIRouter(prefix="/users", tags=["Users"])


# -------------------------------------------------
@users_router.get("/roles")
async def list_roles():
    roles_list = [item.value for item in Role]
    return roles_list


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
