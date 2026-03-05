from typing import Annotated, Any, List, Optional, Type

from fastapi import APIRouter, Depends

from ..utils import RouteReturnSchema
from .base_service import BaseService


# -------------------------------------------------
class GenericRouterFactory:
    def __init__(
        self,
        service_dependency: Any,
        report_schema: Type,  # Esquema para la ruta de inserción masiva
        full_filter_schema: Type,
        lite_filter_schema: Type,  # Nuevo esquema para exportar
        prefix: str,
        tags: Optional[List[str]] = None,
    ):
        # Si tags es None, no pasamos nada al APIRouter,
        # así no genera el tag automático del prefix.
        router_args = {"prefix": prefix}
        if tags:
            router_args["tags"] = tags

        self.router = APIRouter(**router_args)
        self.service_dep = service_dependency
        self.report_schema = report_schema
        self.full_filter_schema = full_filter_schema
        self.lite_filter_schema = lite_filter_schema
        self._setup_routes()

    # -------------------------------------------------
    def _setup_routes(self):
        """Define las rutas estándar para todos los servicios"""

        # -------------------------------------------------
        @self.router.get("/", name="Get All")
        async def get_all(
            params: Annotated[Any, Depends(self.full_filter_schema)],
            service: Annotated[BaseService, Depends(self.service_dep)],
        ):

            return await service.get_all(params)

        # -------------------------------------------------
        @self.router.post(
            "/",
            name="Add Many",
            # 💡 Truco Maestro: Inyectamos el esquema de Rf602Report en Swagger
            responses={200: {"model": self.report_schema}},
            openapi_extra={
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {
                                    "$ref": f"#/components/schemas/{self.report_schema.__name__}"
                                },
                            }
                        }
                    }
                }
            },
        )
        async def add_many(
            data: List[dict],
            service: Annotated[BaseService, Depends(self.service_dep)],
        ):
            return await service.add_many(data)

        # -------------------------------------------------
        @self.router.delete("/", name="Delete Many", response_model=RouteReturnSchema)
        async def delete_many(
            # Esto expande los campos del filtro (ej. ejercicio, estructura) en Swagger
            params: Annotated[Any, Depends(self.lite_filter_schema)],
            service: Annotated[BaseService, Depends(self.service_dep)],
        ):
            return await service.delete_many(params)

        # -------------------------------------------------
        @self.router.get("/export", name="Export to Google Sheets and Excel")
        async def export(
            params: Annotated[Any, Depends(self.lite_filter_schema)],
            service: Annotated[BaseService, Depends(self.service_dep)],
        ):
            return await service.export(params)

    # -------------------------------------------------
    def get_router(self) -> APIRouter:
        return self.router
