from typing import Annotated, Any, List, Optional, Type

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from .base_service import BaseService


# -------------------------------------------------
class GenericRouterFactory:
    def __init__(
        self,
        service_dependency: Any,
        report_schema: Type,  # Esquema para la ruta de inserción masiva
        filter_schema: Type,
        export_schema: Type,  # Nuevo esquema para exportar
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
        self.filter_schema = filter_schema
        self.export_schema = export_schema
        self._setup_routes()

    # -------------------------------------------------
    def _setup_routes(self):
        """Define las rutas estándar para todos los servicios"""

        # -------------------------------------------------
        @self.router.get("/", name="Get All")
        async def get_all(
            params: Annotated[Any, Depends(self.filter_schema)],
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
            # Para que el $ref funcione en Swagger, FastAPI necesita conocer el modelo.
            # Asegúrate de incluirlo en el response_model de alguna ruta o agrégalo
            # manualmente a la app de FastAPI al inicio:
            # main.py o donde inicies la app
            # from modules.rf602.schemas import Rf602Report
            # # Esto asegura que el esquema esté disponible para las referencias del Factory
            # app.openapi_schema["components"]["schemas"]["Rf602Report"] = Rf602Report.model_json_schema()
        )
        async def add_many(
            data: List[dict],  # type: ignore
            service: Annotated[BaseService, Depends(self.service_dep)],
        ):
            try:
                # Podrías pasar parámetros extra aquí si el servicio los requiere
                return await service.add_many(data)
            except HTTPException as e:
                return JSONResponse(
                    content={"error": e.detail}, status_code=e.status_code
                )

        # -------------------------------------------------
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

        # -------------------------------------------------
        @self.router.get("/export", name="Export to Google Sheets and Excel")
        async def export(
            params: Annotated[Any, Depends(self.export_schema)],
            service: Annotated[BaseService, Depends(self.service_dep)],
        ):
            return await service.export(params)

    # -------------------------------------------------
    def get_router(self) -> APIRouter:
        return self.router
