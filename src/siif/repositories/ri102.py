__all__ = ["Ri102RepositoryDependency", "Ri102Repository"]

from typing import Annotated

from fastapi import Depends

from ...config import BaseRepository
from ..schemas import Ri102Document


class Ri102Repository(BaseRepository[Ri102Document]):
    collection_name = "siif_ri102"
    model = Ri102Document


Ri102RepositoryDependency = Annotated[Ri102Repository, Depends()]
