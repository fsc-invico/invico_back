__all__ = ["FacturerosRepositoryDependency", "FacturerosRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import FacturerosDocument


class FacturerosRepository(BaseRepository[FacturerosDocument]):
    collection_name = "slave_factureros"
    model = FacturerosDocument


FacturerosRepositoryDependency = Annotated[FacturerosRepository, Depends()]
