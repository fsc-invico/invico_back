from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    SaldosBarriosEvolucionDocument,
    SaldosBarriosEvolucionFullFilter,
    SaldosBarriosEvolucionLiteFilter,
)
from ..services import (
    SaldosBarriosEvolucionService,
    SaldosBarriosEvolucionServiceDependency,
)  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=SaldosBarriosEvolucionService,
    report_schema=SaldosBarriosEvolucionDocument,
    full_filter_schema=SaldosBarriosEvolucionFullFilter,  # Usa limit/offset
    lite_filter_schema=SaldosBarriosEvolucionLiteFilter,  # No usa limit/offset
    prefix="/saldosBarriosEvolucion",
)

saldos_barrios_evolucion_router = factory.get_router()


# -------------------------------------------------
@saldos_barrios_evolucion_router.get(
    "/uniqueCodBarrios",
    description="Get All Cod. Barrios",
    response_model=list[str],
)
async def desc_estructuras(
    # params: Annotated[Rf610FullFilter, Depends()],
    service: SaldosBarriosEvolucionServiceDependency,
):
    return await service.unique_cod_barrios()
