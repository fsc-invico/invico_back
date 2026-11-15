from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    CtasCtesDocument,
    CtasCtesFullFilter,
    CtasCtesLiteFilter,
    CtasCtesReport,
)
from ..services import CtasCtesService, CtasCtesServiceDependency  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=CtasCtesService,
    report_schema=CtasCtesDocument,
    full_filter_schema=CtasCtesFullFilter,  # Usa limit/offset
    lite_filter_schema=CtasCtesLiteFilter,  # No usa limit/offset
    prefix="/ctasCtes",
)

ctas_ctes_router = factory.get_router()


# -------------------------------------------------
@ctas_ctes_router.post("/add_one", response_model=CtasCtesDocument)
async def add_one(
    payload: CtasCtesReport,
    service: CtasCtesServiceDependency,
    security: AuthorizationDependency,
) -> CtasCtesDocument:
    """Alta individual de una cuenta corriente (solo administradores)."""
    security.is_admin_or_raise()
    return await service.add_one(cta_cte=payload)


# -------------------------------------------------
@ctas_ctes_router.put("/update_one/{id}", response_model=CtasCtesDocument)
async def update_one(
    id: str,
    data: CtasCtesReport,
    service: CtasCtesServiceDependency,
    security: AuthorizationDependency,
) -> CtasCtesDocument:
    """Edición individual con cerrojo de concurrencia (solo administradores)."""
    security.is_admin_or_raise()
    return await service.update_one_safely(id=id, data=data)


# -------------------------------------------------
@ctas_ctes_router.delete("/delete_one/{id}", response_model=CtasCtesDocument)
async def delete_one(
    id: str,
    service: CtasCtesServiceDependency,
    security: AuthorizationDependency,
) -> CtasCtesDocument:
    """Baja individual de una cuenta corriente (solo administradores)."""
    security.is_admin_or_raise()
    return await service.delete_one(id=id)

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# banco_invico_router = factory.get_router()


# @banco_invico_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
