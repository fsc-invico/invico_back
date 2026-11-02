"""
Migra la colección 'users' al esquema de múltiples roles.

Convierte el campo legacy (string):

    { "role": "admin" }

en el nuevo campo (lista):

    { "roles": ["admin"] }

También elimina el campo legacy 'role' en los documentos que ya
tengan 'roles'. Ejecutar una vez junto con el deploy del cambio:

    poetry run python -m scripts.migrate_roles
"""

import asyncio

from pymongo.errors import PyMongoError

from src.config import Database


# -------------------------------------------------
async def main() -> None:
    Database.initialize()
    try:
        await Database.client.admin.command("ping")
        print("Connected to MongoDB")
    except PyMongoError as e:
        print("Error connecting to MongoDB:", e)
        return

    users_collection = Database.db["users"]

    # 1. Documentos legacy: role (str) -> roles (list) y eliminamos role
    legacy_result = await users_collection.update_many(
        {"roles": {"$exists": False}, "role": {"$type": "string"}},
        [
            {"$set": {"roles": ["$role"]}},
            {"$unset": "role"},
        ],
    )
    print(f"Documentos migrados a lista de roles: {legacy_result.modified_count}")

    # 2. Limpieza: documentos con 'roles' nuevo que aún conservan 'role' viejo
    stale_result = await users_collection.update_many(
        {"roles": {"$exists": True}, "role": {"$exists": True}},
        [{"$unset": "role"}],
    )
    print(f"Campo legacy 'role' eliminado: {stale_result.modified_count}")


# -------------------------------------------------
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

    # poetry run python -m scripts.migrate_roles
