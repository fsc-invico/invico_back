from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from .base_service import BaseService


class GenericRouterFactory:
    def __init__(
        self, service_dependency: Any, prefix: str, tags: Optional[List[str]] = None
    ):
        # Si tags es None, no pasamos nada al APIRouter,
        # así no genera el tag automático del prefix.
        router_args = {"prefix": prefix}
        if tags:
            router_args["tags"] = tags

        self.router = APIRouter(**router_args)
        self.service_dep = service_dependency
        self._setup_routes()

    def _setup_routes(self, name="Get All"):
        """Define las rutas estándar para todos los servicios"""

        @self.router.get("/")
        async def get_all(service: Annotated[BaseService, Depends(self.service_dep)]):
            return await service.get_all()

        @self.router.post("/", name="Add Many")
        async def add_many(service: Annotated[BaseService, Depends(self.service_dep)]):
            try:
                return await service.add_many()
            except HTTPException as e:
                return JSONResponse(
                    content={"error": e.detail}, status_code=e.status_code
                )

        @self.router.delete("/", name="Delete Many")
        async def delete_many(
            service: Annotated[BaseService, Depends(self.service_dep)],
        ):
            try:
                return await service.delete_many()
            except HTTPException as e:
                return JSONResponse(
                    content={"error": e.detail}, status_code=e.status_code
                )

        @self.router.get("/export", name="Export to Excel")
        async def export(
            service: Annotated[BaseService, Depends(self.service_dep)],
            ejercicio: Optional[int] = None,
        ):
            return await service.export(ejercicio)

    def get_router(self) -> APIRouter:
        return self.router
