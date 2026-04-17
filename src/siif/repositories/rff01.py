__all__ = ["Rff01RepositoryDependency", "Rff01Repository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Rff01Document


class Rff01Repository(BaseRepository[Rff01Document]):
    collection_name = "siif_rff01"
    model = Rff01Document


Rff01RepositoryDependency = Annotated[Rff01Repository, Depends()]
