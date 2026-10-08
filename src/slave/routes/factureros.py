from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    FacturerosDocument,
    FacturerosFullFilter,
    FacturerosLiteFilter,
    FacturerosReport,
)
from ..services import FacturerosService, FacturerosServiceDependency

factory = GenericRouterFactory(
    service_dependency=FacturerosService,
    report_schema=FacturerosDocument,
    full_filter_schema=FacturerosFullFilter,  # Usa limit/offset
    lite_filter_schema=FacturerosLiteFilter,  # No usa limit/offset
    prefix="/factureros",
)

factureros_router = factory.get_router()


# -------------------------------------------------
@factureros_router.post("/add_one")
async def add_one(
    payload: FacturerosReport,
    service: FacturerosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_one(facturero=payload)


# -------------------------------------------------
@factureros_router.put("/update_one/{id}", response_model=FacturerosDocument)
async def update_one(
    id: str,
    data: FacturerosReport,
    service: FacturerosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.update_one_safely(id=id, data=data)


# -------------------------------------------------
@factureros_router.delete("/delete_one/{id}", response_model=FacturerosDocument)
async def delete_one(
    id: str, service: FacturerosServiceDependency, security: AuthorizationDependency
):
    security.is_admin_or_user_or_raise()
    return await service.delete_one(id=id)


# -------------------------------------------------
@factureros_router.get("/actividades")
async def get_actividades(
    service: FacturerosServiceDependency,
):
    return await service.get_actividades()


# -------------------------------------------------
@factureros_router.get("/partidas")
async def get_partidas(
    service: FacturerosServiceDependency,
):
    return await service.get_partidas()
