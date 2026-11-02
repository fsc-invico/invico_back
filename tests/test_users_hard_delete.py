"""Tests del hard delete de usuarios (DELETE /users/delete_hard/{id}).

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_users_hard_delete -v
"""

import asyncio
import unittest

from bson import ObjectId
from fastapi import HTTPException

from src.auth.routes.users import delete_user_hard
from src.auth.services.auth import Authorization
from src.auth.services.users import UsersService


# -------------------------------------------------
class FakeCredentials:
    """Stub mínimo de JwtAuthorizationCredentials para tests."""

    def __init__(self, subject: dict) -> None:
        self.subject = subject


# -------------------------------------------------
def make_authorization(subject: dict) -> Authorization:
    return Authorization(FakeCredentials(subject))  # type: ignore[arg-type]


# -------------------------------------------------
class FakeUsersRepository:
    """Stub mínimo de UsersRepository para tests."""

    def __init__(self, document: dict | None) -> None:
        self.document = document
        self.deleted_ids: list[ObjectId] = []

    async def delete_by_id(self, id: ObjectId) -> dict | None:
        self.deleted_ids.append(id)
        return self.document


# -------------------------------------------------
class FakeCredentialsRepository:
    """Stub mínimo de CredentialsRepository para tests."""

    def __init__(self) -> None:
        self.filters: list[dict] = []

    async def delete_by_fields(self, fields: dict) -> int:
        self.filters.append(fields)
        return 1


# -------------------------------------------------
def make_service(
    document: dict | None,
) -> tuple[UsersService, FakeUsersRepository, FakeCredentialsRepository]:
    fake_users = FakeUsersRepository(document)
    fake_creds = FakeCredentialsRepository()
    service = UsersService(users=fake_users, external_creds=fake_creds)  # type: ignore[arg-type]
    return service, fake_users, fake_creds


USER_ID = ObjectId("64b000000000000000000001")
USER_DOCUMENT = {
    "_id": USER_ID,
    "username": "fer",
    "roles": ["admin"],
    "hash_password": "secreto-hasheado",
}


# -------------------------------------------------
class TestDeleteOneHardService(unittest.TestCase):
    """Valida el método UsersService.delete_one_hard."""

    # -------------------------------------------------
    def test_delete_one_hard_removes_user_and_credentials(self) -> None:
        """Borra el usuario y, en cascada, sus credenciales externas."""
        service, fake_users, fake_creds = make_service(USER_DOCUMENT)

        result = asyncio.run(service.delete_one_hard(user_id=USER_ID))

        self.assertIn("message", result)
        # Nunca debe devolver el hash de la contraseña
        self.assertNotIn("hash_password", str(result))
        self.assertEqual(fake_users.deleted_ids, [USER_ID])
        self.assertEqual(fake_creds.filters, [{"user_id": str(USER_ID)}])

    # -------------------------------------------------
    def test_delete_one_hard_raises_404_when_user_missing(self) -> None:
        """Si el usuario no existe lanza 404 y no toca las credenciales."""
        service, fake_users, fake_creds = make_service(None)

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(service.delete_one_hard(user_id=USER_ID))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(fake_users.deleted_ids, [USER_ID])
        # Sin cascada si el usuario no existía
        self.assertEqual(fake_creds.filters, [])


# -------------------------------------------------
class TestDeleteUserHardRoute(unittest.TestCase):
    """Valida la ruta DELETE /users/delete_hard/{id}."""

    # -------------------------------------------------
    def test_route_rejects_invalid_object_id(self) -> None:
        """Un id que no es un ObjectId válido responde 400."""
        service, fake_users, _ = make_service(None)
        security = make_authorization(
            {"id": "1", "username": "admin", "roles": ["admin"]}
        )

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                delete_user_hard(id="no-es-un-id", users=service, security=security)
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(fake_users.deleted_ids, [])

    # -------------------------------------------------
    def test_route_requires_admin_role(self) -> None:
        """Un usuario sin rol 'admin' recibe 403 y no borra nada."""
        service, fake_users, _ = make_service(USER_DOCUMENT)
        security = make_authorization({"id": "1", "username": "fer", "roles": ["user"]})

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                delete_user_hard(id=str(USER_ID), users=service, security=security)
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(fake_users.deleted_ids, [])

    # -------------------------------------------------
    def test_route_blocks_self_deletion(self) -> None:
        """Un admin no puede eliminar su propia cuenta (400, sin borrar nada)."""
        service, fake_users, fake_creds = make_service(USER_DOCUMENT)
        security = make_authorization(
            {"id": str(USER_ID), "username": "admin", "roles": ["admin"]}
        )

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                delete_user_hard(id=str(USER_ID), users=service, security=security)
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(fake_users.deleted_ids, [])
        self.assertEqual(fake_creds.filters, [])

    # -------------------------------------------------
    def test_route_deletes_user_on_success(self) -> None:
        """Un admin con id válido delega en el servicio y recibe el mensaje."""
        service, fake_users, fake_creds = make_service(USER_DOCUMENT)
        security = make_authorization(
            {"id": "1", "username": "admin", "roles": ["admin"]}
        )

        result = asyncio.run(
            delete_user_hard(id=str(USER_ID), users=service, security=security)
        )

        self.assertIn("message", result)
        self.assertEqual(fake_users.deleted_ids, [USER_ID])
        self.assertEqual(fake_creds.filters, [{"user_id": str(USER_ID)}])


# -------------------------------------------------
if __name__ == "__main__":
    unittest.main()
