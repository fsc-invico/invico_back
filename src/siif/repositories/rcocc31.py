__all__ = ["Rcocc31RepositoryDependency", "Rcocc31Repository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Rcocc31Document


class Rcocc31Repository(BaseRepository[Rcocc31Document]):
    collection_name = "siif_rcocc31"
    model = Rcocc31Document


Rcocc31RepositoryDependency = Annotated[Rcocc31Repository, Depends()]
