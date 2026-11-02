"""Tests del esquema de múltiples roles y los guards de autorización.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_auth_roles -v
"""

import unittest

from fastapi import HTTPException
from pydantic import ValidationError

from src.auth.schemas import (
    CreateUser,
    PrivateUser,
    PublicStoredUser,
    RegisterUser,
    Role,
    UpdateUserRole,
)
from src.auth.services.auth import Authorization


# -------------------------------------------------
class FakeCredentials:
    """Stub mínimo de JwtAuthorizationCredentials para tests."""

    def __init__(self, subject: dict) -> None:
        self.subject = subject


# -------------------------------------------------
def make_authorization(subject: dict) -> Authorization:
    return Authorization(FakeCredentials(subject))  # type: ignore[arg-type]


# -------------------------------------------------
class TestRoleSchemas(unittest.TestCase):
    """Valida el esquema Role y la coerción backward-compatible."""

    # -------------------------------------------------
    def test_role_enum_contains_new_roles(self) -> None:
        self.assertEqual(
            {role.value for role in Role},
            {"admin", "user", "pending", "eecc", "icaro"},
        )

    # -------------------------------------------------
    def test_public_user_accepts_roles_list(self) -> None:
        user = PublicStoredUser(id="1", username="fer", roles=["user", "eecc"])
        self.assertEqual(user.roles, [Role.user, Role.eecc])

    # -------------------------------------------------
    def test_public_user_coerces_legacy_role_string(self) -> None:
        """Documentos viejos con role: "admin" deben validar como lista."""
        user = PublicStoredUser.model_validate(
            {"id": "1", "username": "fer", "role": "admin"}
        )
        self.assertEqual(user.roles, [Role.admin])

    # -------------------------------------------------
    def test_create_user_defaults_to_user(self) -> None:
        user = CreateUser(username="fer", password="secret")
        self.assertEqual(user.roles, [Role.user])

    # -------------------------------------------------
    def test_create_user_accepts_multiple_roles(self) -> None:
        user = CreateUser(
            username="fer", password="secret", roles=["user", "eecc", "icaro"]
        )
        self.assertEqual(user.roles, [Role.user, Role.eecc, Role.icaro])

    # -------------------------------------------------
    def test_create_user_rejects_empty_roles(self) -> None:
        with self.assertRaises(ValueError):
            CreateUser(username="fer", password="secret", roles=[])

    # -------------------------------------------------
    def test_create_user_rejects_duplicated_roles(self) -> None:
        with self.assertRaises(ValueError):
            CreateUser(username="fer", password="secret", roles=["user", "user"])

    # -------------------------------------------------
    def test_pending_role_is_exclusive(self) -> None:
        with self.assertRaises(ValueError):
            CreateUser(username="fer", password="secret", roles=["pending", "eecc"])
        user = CreateUser(username="fer", password="secret", roles=["pending"])
        self.assertEqual(user.roles, [Role.pending])

    # -------------------------------------------------
    def test_update_user_role_rejects_pending_combination(self) -> None:
        with self.assertRaises(ValueError):
            UpdateUserRole(roles=["pending", "user"])

    # -------------------------------------------------
    def test_register_flow_keeps_pending(self) -> None:
        """RegisterUser -> model_dump -> PrivateUser (flujo de create_one)."""
        registration = RegisterUser(username="fer", password="secret")
        dump = registration.model_dump(exclude={"password"})
        self.assertEqual(dump["roles"], ["pending"])

        private_user = PrivateUser.model_validate({**dump, "hash_password": "hashed"})
        self.assertEqual(private_user.roles, [Role.pending])

    # -------------------------------------------------
    def test_create_user_rejects_invalid_role(self) -> None:
        with self.assertRaises(ValidationError):
            CreateUser(username="fer", password="secret", roles=["no_existe"])


# -------------------------------------------------
class TestAuthorizationGuards(unittest.TestCase):
    """Valida los guards de Authorization con el nuevo formato de lista."""

    # -------------------------------------------------
    def test_legacy_role_payload_is_supported(self) -> None:
        auth = make_authorization({"id": "1", "username": "fer", "role": "admin"})
        self.assertEqual(auth.roles, ["admin"])
        self.assertTrue(auth.is_admin)
        auth.is_admin_or_raise()  # no debe lanzar

    # -------------------------------------------------
    def test_admin_check_with_multiple_roles(self) -> None:
        auth = make_authorization({"id": "1", "roles": ["user", "eecc"]})
        self.assertFalse(auth.is_admin)
        self.assertTrue(auth.is_user)
        with self.assertRaises(HTTPException):
            auth.is_admin_or_raise()

    # -------------------------------------------------
    def test_admin_or_user_allows_admin_and_user(self) -> None:
        make_authorization({"roles": ["admin"]}).is_admin_or_user_or_raise()
        make_authorization({"roles": ["icaro", "user"]}).is_admin_or_user_or_raise()

    # -------------------------------------------------
    def test_admin_or_user_blocks_pending(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            make_authorization({"roles": ["pending"]}).is_admin_or_user_or_raise()
        self.assertEqual(ctx.exception.status_code, 403)

    # -------------------------------------------------
    def test_admin_or_user_blocks_role_only_eecc(self) -> None:
        """Sin 'user' ni 'admin', los reportes requieren aprobación."""
        with self.assertRaises(HTTPException):
            make_authorization({"roles": ["eecc"]}).is_admin_or_user_or_raise()

    # -------------------------------------------------
    def test_require_any_role(self) -> None:
        auth = make_authorization({"roles": ["user", "eecc"]})
        auth.require_any_role("eecc")  # no debe lanzar
        with self.assertRaises(HTTPException) as ctx:
            auth.require_any_role("icaro")
        self.assertEqual(ctx.exception.status_code, 403)

    # -------------------------------------------------
    def test_empty_roles_are_denied(self) -> None:
        auth = make_authorization({})
        self.assertEqual(auth.roles, [])
        with self.assertRaises(HTTPException):
            auth.is_admin_or_user_or_raise()


# -------------------------------------------------
if __name__ == "__main__":
    unittest.main()
