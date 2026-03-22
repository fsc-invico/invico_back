__all__ = ["Rdeu012RepositoryDependency", "Rdeu012Repository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Rdeu012Document


class Rdeu012Repository(BaseRepository[Rdeu012Document]):
    collection_name = "siif_rdeu012"
    model = Rdeu012Document


Rdeu012RepositoryDependency = Annotated[Rdeu012Repository, Depends()]
