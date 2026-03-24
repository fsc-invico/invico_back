__all__ = ["CtasCtesRepositoryDependency", "CtasCtesRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import CtasCtesDocument


class CtasCtesRepository(BaseRepository[CtasCtesDocument]):
    collection_name = "icaro_ctas_ctes"
    model = CtasCtesDocument


CtasCtesRepositoryDependency = Annotated[CtasCtesRepository, Depends()]
