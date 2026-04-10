__all__ = ["InformeContableRepositoryDependency", "InformeContableRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import InformeContableDocument


class InformeContableRepository(BaseRepository[InformeContableDocument]):
    collection_name = "sgf_informe_contable"
    model = InformeContableDocument


InformeContableRepositoryDependency = Annotated[InformeContableRepository, Depends()]
