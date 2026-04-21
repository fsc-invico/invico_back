from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    CargaDocument,
    CargaFullFilter,
    CargaLiteFilter,
    CargaReport,
)
from ..services import CargaService, CargaServiceDependency  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=CargaService,
    report_schema=CargaDocument,
    full_filter_schema=CargaFullFilter,  # Usa limit/offset
    lite_filter_schema=CargaLiteFilter,  # No usa limit/offset
    prefix="/carga",
)

carga_router = factory.get_router()


# -------------------------------------------------
@carga_router.post("/add_one")
async def add_one(data: CargaReport, service: CargaServiceDependency):
    return await service.add_one(data)


# -------------------------------------------------
@carga_router.put("/{id}")
async def update_one(id: str, data: CargaReport, service: CargaServiceDependency):
    return await service.update_one_safely(id = id, data = data)