__all__ = ["Rci02RepositoryDependency", "Rci02Repository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Rci02Document


class Rci02Repository(BaseRepository[Rci02Document]):
    collection_name = "siif_rci02"
    model = Rci02Document


Rci02RepositoryDependency = Annotated[Rci02Repository, Depends()]
