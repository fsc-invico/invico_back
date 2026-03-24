__all__ = ["SubprogramasRepositoryDependency", "SubprogramasRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import SubprogramasDocument


class SubprogramasRepository(BaseRepository[SubprogramasDocument]):
    collection_name = "icaro_subprogramas"
    model = SubprogramasDocument


SubprogramasRepositoryDependency = Annotated[SubprogramasRepository, Depends()]
