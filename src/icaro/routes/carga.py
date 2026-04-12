from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    CargaDocument,
    CargaFullFilter,
    CargaLiteFilter,
)
from ..services import CargaService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=CargaService,
    report_schema=CargaDocument,
    full_filter_schema=CargaFullFilter,  # Usa limit/offset
    lite_filter_schema=CargaLiteFilter,  # No usa limit/offset
    prefix="/carga",
)

carga_router = factory.get_router()


@carga_router.post("/add_one")
async def add_one():
    return {"stats": "data"}
