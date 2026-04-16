__all__ = ["Rog01RepositoryDependency", "Rog01Repository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Rog01Document


class Rog01Repository(BaseRepository[Rog01Document]):
    collection_name = "siif_rog01"
    model = Rog01Document


Rog01RepositoryDependency = Annotated[Rog01Repository, Depends()]
