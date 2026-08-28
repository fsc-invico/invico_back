__all__ = ["HonorariosRepositoryDependency", "HonorariosRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import HonorariosDocument


class HonorariosRepository(BaseRepository[HonorariosDocument]):
    collection_name = "slave_honorarios"
    model = HonorariosDocument


HonorariosRepositoryDependency = Annotated[HonorariosRepository, Depends()]
