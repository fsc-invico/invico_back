__all__ = ["ResumenRendObrasRepositoryDependency", "ResumenRendObrasRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ResumenRendObrasDocument


class ResumenRendObrasRepository(BaseRepository[ResumenRendObrasDocument]):
    collection_name = "icaro_resumen_rend_obras"
    model = ResumenRendObrasDocument


ResumenRendObrasRepositoryDependency = Annotated[ResumenRendObrasRepository, Depends()]
