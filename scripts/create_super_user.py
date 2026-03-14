"""
This script requires the file ADMIN_USER_CONF to be in the same directory as the
script. Or you can set the username and password environment variables.
"""

import asyncio

from fastapi import HTTPException

from src.auth.repositories import UsersRepository
from src.auth.schemas import CreateUser
from src.auth.services import UsersService
from src.config import Database, settings


# -------------------------------------------------
async def main():
    Database.initialize()
    try:
        await Database.client.admin.command("ping")
        print("Connected to MongoDB")
    except Exception as e:
        print("Error connecting to MongoDB:", e)
        return

    data = {}
    try:
        with open("scripts/ADMIN_USER_CONF", "r") as f:
            for line in f:
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = v.strip()
    except FileNotFoundError:
        admin_username = str(settings.ADMIN_USERNAME).strip()
        admin_pass = str(settings.ADMIN_PASSWORD).strip()

        data = dict(
            username=admin_username,
            password=admin_pass,
        )

    # 🛡️ VALIDACIÓN DE SEGURIDAD PARA BCRYPT
    # Convertimos a bytes para medir el tamaño real que ve la librería
    pass_bytes = data["password"].encode("utf-8")

    if len(pass_bytes) > 72:
        print(f"Alerta: La contraseña supera los 72 bytes ({len(pass_bytes)} bytes).")
        # Truncamos físicamente a 72 bytes, no solo caracteres
        data["password"] = pass_bytes[:72].decode("utf-8", "ignore")

    # Limpieza crítica
    if not data.get("password"):
        print("Error: No se encontró contraseña en la configuración.")
        return

    data["role"] = "admin"
    # Aseguramos el límite de bcrypt
    if len(data["password"]) > 72:
        data["password"] = data["password"][:72]

    try:
        insertion_user = CreateUser.model_validate(data)
        users_service = UsersService(users=UsersRepository(), external_creds=None)
        result = await users_service.create_one(user=insertion_user)
        print(f"Super user {data['username']} creado con id: {result.id}")
    except HTTPException as e:
        if e.status_code == 409:
            print("El superusuario ya existe.")
        else:
            print(f"Error HTTP: {e.detail}")
    except Exception as e:
        print(f"Error inesperado: {e}")


# -------------------------------------------------
if __name__ == "__main__":
    # try:
    #     loop = asyncio.get_running_loop()
    # except RuntimeError:
    #     loop = asyncio.new_event_loop()
    #     asyncio.set_event_loop(loop)

    # loop.run_until_complete(main())

    # Forma moderna de correr asyncio en scripts de Python 3.7+
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

    # poetry run python -m scripts.create_super_user
