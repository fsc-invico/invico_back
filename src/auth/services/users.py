__all__ = ["UsersService", "UsersServiceDependency"]

from dataclasses import dataclass
from typing import Annotated, List, Optional

from bson import ObjectId
from fastapi import Depends, HTTPException, status

from ...config import logger
from ...utils import BaseFilterParams, CryptoManager, PyObjectId
from ..repositories import (
    CredentialsRepositoryDependency,
    UsersRepositoryDependency,
)
from ..schemas import (
    CreateUser,
    ExternalCredentialIn,
    PrivateStoredUser,
    PrivateUser,
    PublicStoredUser,
)

# from ..utils import validate_and_extract_data
from .auth import Authentication


# -------------------------------------------------
@dataclass
class UsersService:
    users: UsersRepositoryDependency
    external_creds: CredentialsRepositoryDependency

    # -------------------------------------------------
    async def create_one(self, user: CreateUser) -> PublicStoredUser:
        """Create a new user"""
        existing_user = await self.users.get_one_by_fields({"username": user.username})
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

        if db_user := await self.users.get_one_by_fields_or(search_query):
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
    async def approve_user(self, user_id: PyObjectId):

        # 1. Intentamos actualizar SOLO si el rol actual es 'pending'
        # Esto evita que 'aprove' cambie el rol de un admin o un usuario ya activo
        result = await self.users.update_one(
            {"_id": user_id, "role": "pending"}, {"$set": {"role": "user"}}
        )

        if result.modified_count == 0:
            # 2. Si no hubo cambios, investigamos por qué
            user = await self.users.get_by_id(user_id)

            if not user:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")

            if user.get("role") != "pending":
                return {
                    "message": f"El usuario ya está activo con el rol '{user.get('role')}'"
                }

        return {"message": f"Usuario {user_id} aprobado exitosamente."}

    # -------------------------------------------------
    async def get_all(self, params: BaseFilterParams) -> List[PublicStoredUser]:
        """Get all users"""
        try:
            # 1. Obtenemos la lista de documentos (diccionarios con ObjectId)
            db_users = await self.users.find_with_filter_params(params=params)
            # Agregamos un print para debuggear qué está llegando realmente
            # logger.info(f"Primer objeto recibido del repo: {type(db_users[0])}")
            # logger.info(
            #     f"Contenido: {db_users[0]}"
            # )  # Úsalo solo si no hay datos sensibles

            # 2. Los validamos y transformamos usando el esquema
            # Pydantic convertirá automáticamente los _id (ObjectId) a id (str)
            return [PublicStoredUser.model_validate(user) for user in db_users]

        except Exception as e:
            logger.error(f"¡CAPTURADO!: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error al obtener usuarios: {str(e)}",
            )

    # -------------------------------------------------
    async def add_external_credential(self, user_id: str, data: ExternalCredentialIn):
        try:
            crypto = CryptoManager()

            # 1. Ciframos el password sensible
            encrypted_pw = crypto.encrypt_password(data.password)

            # 2. Definimos el filtro (para que cada usuario tenga solo 1 clave por sistema)
            # Usamos el string del ID de usuario
            filter_query = {
                "user_id": user_id,
                "system_name": data.system_name.lower().strip(),
            }

            # 3. Datos a guardar
            update_data = {
                "external_username": data.external_username,
                "encrypted_pass": encrypted_pw,
            }

            # 4. Usamos tu nuevo método del repositorio
            # Asumiendo que 'self.external_creds' es el repositorio de la nueva colección
            success = await self.external_creds.update_one(
                filter=filter_query, update_data=update_data, upsert=True
            )

            if success:
                return {
                    "message": f"Credenciales para {data.system_name} guardadas con éxito."
                }
            return {
                "message": "No se realizaron cambios (los datos ya eran idénticos)."
            }

        except Exception as e:
            logger.error(f"Error guardando credencial externa: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Error interno al cifrar/guardar"
            )

    # -------------------------------------------------
    async def get_decrypted_credential(self, user_id: str, system_name: str):
        # 1. Buscar en la colección 'external_credentials'
        cred = await self.external_creds.get_one_by_fields(
            {"user_id": user_id, "system_name": system_name}
        )

        if not cred:
            raise HTTPException(status_code=404, detail="Credencial no encontrada")

        # 2. Descifrar usando nuestra CryptoManager
        crypto = CryptoManager()
        return {
            "external_username": cred["external_username"],
            "external_password": crypto.decrypt_password(cred["encrypted_pass"]),
        }

    # -------------------------------------------------
    async def get_all_user_credentials(self, user_id: str):
        """Lista las credenciales configuradas (sin los passwords planos)"""
        # Buscamos todas las credenciales vinculadas a ese user_id
        creds_cursor = await self.external_creds.get_many_by_fields(
            {"user_id": user_id}
        )

        # Devolvemos una lista limpia (metadata)
        return [
            {
                "system_name": c["system_name"],
                "username": c["external_username"],
            }
            for c in creds_cursor
        ]

    # -------------------------------------------------
    async def delete_user_credential(self, user_id: str, system_name: str):
        """Elimina una credencial específica"""
        result = await self.external_creds.delete_by_fields(
            {"user_id": user_id, "system_name": system_name.lower().strip()}
        )

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Credencial no encontrada")

        return {"message": f"Credencial para {system_name} eliminada con éxito."}

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
