__all__ = ["ResumenRendProvRepositoryDependency", "ResumenRendProvRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ResumenRendProvDocument


class ResumenRendProvRepository(BaseRepository[ResumenRendProvDocument]):
    collection_name = "sgf_resumen_rend_prov"
    model = ResumenRendProvDocument


ResumenRendProvRepositoryDependency = Annotated[ResumenRendProvRepository, Depends()]
