__all__ = ["ObrasRepositoryDependency", "ObrasRepository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import ObrasDocument


class ObrasRepository(BaseRepository[ObrasDocument]):
    collection_name = "icaro_obras"
    model = ObrasDocument


ObrasRepositoryDependency = Annotated[ObrasRepository, Depends()]
