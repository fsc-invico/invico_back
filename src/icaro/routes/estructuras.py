from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    EstructurasDocument,
    EstructurasFullFilter,
    EstructurasLiteFilter,
    EstructurasReport,
)
from ..services import EstructurasService, EstructurasServiceDependency

factory = GenericRouterFactory(
    service_dependency=EstructurasService,
    report_schema=EstructurasDocument,
    full_filter_schema=EstructurasFullFilter,  # Usa limit/offset
    lite_filter_schema=EstructurasLiteFilter,  # No usa limit/offset
    prefix="/estructuras",
)

estructuras_router = factory.get_router()


# -------------------------------------------------
@estructuras_router.post("/add_one")
async def add_one_obra(
    payload: EstructurasReport,
    service: EstructurasServiceDependency,
):
    return await service.add_one(obra=payload)


# -------------------------------------------------
@estructuras_router.put("/update_one/{id}", response_model=EstructurasDocument)
async def update_one(
    id: str, data: EstructurasReport, service: EstructurasServiceDependency
):
    return await service.update_one_safely(id=id, data=data)


# -------------------------------------------------
@estructuras_router.delete("/delete_one/{id}", response_model=EstructurasDocument)
async def delete_one(id: str, service: EstructurasServiceDependency):
    return await service.delete_one(id=id)
