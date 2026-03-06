__all__ = ["UsersService", "UsersServiceDependency"]

from dataclasses import dataclass
from typing import Annotated, List

from bson import ObjectId
from fastapi import Depends, HTTPException, status

from ...config import logger
from ...utils import BaseFilterParams, PyObjectId
from ..repositories import (
    UsersRepositoryDependency,
)
from ..schemas import (
    CreateUser,
    PrivateStoredUser,
    # UpdateUser,
    PrivateUser,
    PublicStoredUser,
)

# from ..utils import validate_and_extract_data
from .auth import Authentication


# -------------------------------------------------
@dataclass
class UsersService:
    users: UsersRepositoryDependency

    # -------------------------------------------------
    async def create_one(self, user: CreateUser) -> PublicStoredUser:
        """Create a new user"""
        existing_user = await self.users.get_by_fields({"username": user.username})
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="User already exists"
            )

        hash_password = Authentication.get_password_hash(user.password)
        insert_user = user.model_dump(exclude={"password"}, exclude_unset=False)
        insert_user.update(hash_password=hash_password)
        insert_user = PrivateUser.model_validate(insert_user)

        new_user = await self.users.save(insert_user)
        # return new_user
        return PublicStoredUser.model_validate(
            await self.users.get_by_id(new_user.inserted_id)
        )

    # -------------------------------------------------
    async def get_one(
        self,
        *,
        id: str | ObjectId | None = None,  # Aceptamos ambos
        username: str | None = None,
        with_password: bool = False,
    ):
        if all(q is None for q in (id, username)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No id or username provided",
            )

        # Construimos el filtro solo con los valores que existen
        search_query = {}
        if id:
            # 💡 ASEGURAMOS QUE SEA OBJECTID PARA LA DB
            search_query["_id"] = ObjectId(id) if isinstance(id, str) else id
        if username:
            search_query["username"] = username

        if db_user := await self.users.get_by_fields_or(search_query):
            # Si pides password (para login), usas PrivateStoredUser
            if with_password:
                return PrivateStoredUser.model_validate(db_user).model_dump()

            # Para el resto del mundo, PublicStoredUser (Seguro)
            return PublicStoredUser.model_validate(db_user).model_dump()
            # return (
            #     PrivateStoredUser.model_validate(db_user).model_dump()
            #     if with_password
            #     else PublicStoredUser.model_validate(db_user).model_dump()
            # )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # -------------------------------------------------
    async def update_role(self, user_id: PyObjectId, new_role: str):
        # 1. Intentamos actualizar en la base de datos
        result = await self.users.update_one(
            {"_id": user_id}, {"$set": {"role": new_role}}
        )

        if result.modified_count == 0:
            # Verificamos si es que no existe o si ya tenía ese rol
            user = await self.users.get_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
            return {"message": f"El usuario ya tenía el rol {new_role}"}

        return {"message": f"Rol actualizado exitosamente a {new_role}"}

    # -------------------------------------------------
    async def get_all(self, params: BaseFilterParams) -> List[PublicStoredUser]:
        """Get all users"""
        try:
            # 1. Obtenemos la lista de documentos (diccionarios con ObjectId)
            db_users = await self.users.find_with_filter_params(params=params)
            # Agregamos un print para debuggear qué está llegando realmente
            logger.info(f"Primer objeto recibido del repo: {type(db_users[0])}")
            logger.info(
                f"Contenido: {db_users[0]}"
            )  # Úsalo solo si no hay datos sensibles

            # 2. Los validamos y transformamos usando el esquema
            # Pydantic convertirá automáticamente los _id (ObjectId) a id (str)
            return [PublicStoredUser.model_validate(user) for user in db_users]

        except Exception as e:
            logger.error(f"¡CAPTURADO!: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error al obtener usuarios: {str(e)}",
            )

    # @classmethod
    # def get_all_deleted(cls, query: FilterParamsUser) -> dict[str, list]:
    #     """Get all deleted users"""
    #     cursor = query.query_collection(cls.collection, get_deleted=True)
    #     return validate_and_extract_data(cursor, PublicStoredUser)

    # @classmethod
    # def get_all_active(cls, query: FilterParamsUser) -> dict[str, list]:
    #     """Get all active users"""
    #     cursor = query.query_collection(cls.collection, get_deleted=False)
    #     return validate_and_extract_data(cursor, PublicStoredUser)

    # @classmethod
    # def update_one(cls, id: PydanticObjectId, user: UpdateUser, is_admin: bool):
    #     exclude = {"password"} if is_admin else {"password", "role"}
    #     document = cls.collection.find_one_and_update(
    #         {"_id": id},
    #         {"$set": user.model_dump(exclude=exclude, exclude_unset=True)},
    #         return_document=True,
    #     )
    #     if document:
    #         try:
    #             return PublicStoredUser.model_validate(document).model_dump(
    #                 exclude_none=True
    #             )
    #         except ValidationError as e:
    #             raise HTTPException(
    #                 status_code=status.HTTP_204_NO_CONTENT, detail=str(e)
    #             )
    #     else:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
    #         )

    # @classmethod
    # def delete_one(cls, id: PydanticObjectId):
    #     document = cls.collection.find_one_and_update(
    #         {"_id": id},
    #         {"$set": {"deactivated_at": datetime.now()}},
    #         return_document=True,
    #     )
    #     if document:
    #         try:
    #             validated_doc = PublicStoredUser.model_validate(document)
    #             return validated_doc.model_dump()
    #         except ValidationError as e:
    #             raise HTTPException(
    #                 status_code=status.HTTP_204_NO_CONTENT, detail=str(e)
    #             )
    #     else:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
    #         )

    # @classmethod
    # def delete_one_hard(cls, id: PydanticObjectId):
    #     document = cls.collection.find_one_and_delete({"_id": id})
    #     if document:
    #         try:
    #             validated_doc = PublicStoredUser.model_validate(document)
    #             return validated_doc.model_dump()
    #         except ValidationError as e:
    #             raise HTTPException(
    #                 status_code=status.HTTP_204_NO_CONTENT, detail=str(e)
    #             )
    #     else:
    #         raise HTTPException(
    #             status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
    #         )


UsersServiceDependency = Annotated[UsersService, Depends()]
