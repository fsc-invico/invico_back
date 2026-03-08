__all__ = ["CryptoManager"]

from cryptography.fernet import Fernet

from ..config import settings


# -------------------------------------------------
class CryptoManager:
    # -------------------------------------------------
    def __init__(self):
        # La llave debe venir de una variable de entorno (.env)
        # NUNCA la hardcodees en el código
        self.key = settings.SECRET_CRYPTO_KEY
        if not self.key:
            raise ValueError("No se encontró SECRET_CRYPTO_KEY en el entorno")
        self.cipher_suite = Fernet(self.key.encode())

    # -------------------------------------------------
    def encrypt_password(self, raw_password: str) -> str:
        """Convierte texto plano a string cifrado"""
        return self.cipher_suite.encrypt(raw_password.encode()).decode()

    # -------------------------------------------------
    def decrypt_password(self, encrypted_password: str) -> str:
        """Convierte string cifrado a texto plano"""
        return self.cipher_suite.decrypt(encrypted_password.encode()).decode()
