__all__ = ["CertificadosRepositoryDependency", "CertificadosRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import CertificadosDocument


class CertificadosRepository(BaseRepository[CertificadosDocument]):
    collection_name = "icaro_certificados"
    model = CertificadosDocument


CertificadosRepositoryDependency = Annotated[CertificadosRepository, Depends()]
