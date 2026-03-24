__all__ = ["ProgramasRepositoryDependency", "ProgramasRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ProgramasDocument


class ProgramasRepository(BaseRepository[ProgramasDocument]):
    collection_name = "icaro_programas"
    model = ProgramasDocument


ProgramasRepositoryDependency = Annotated[ProgramasRepository, Depends()]
