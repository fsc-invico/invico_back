__all__ = ["Rf602RepositoryDependency", "Rf602Repository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Rf602Document


class Rf602Repository(BaseRepository[Rf602Document]):
    collection_name = "siif_rf602"
    model = Rf602Document


Rf602RepositoryDependency = Annotated[Rf602Repository, Depends()]
