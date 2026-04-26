from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    InformeContableDocument,
    InformeContableFullFilter,
    InformeContableLiteFilter,
    InformeContableUpdateIdCarga,
)
from ..services import InformeContableService, InformeContableServiceDependency

factory = GenericRouterFactory(
    service_dependency=InformeContableService,
    report_schema=InformeContableDocument,
    full_filter_schema=InformeContableFullFilter,  # Usa limit/offset
    lite_filter_schema=InformeContableLiteFilter,  # No usa limit/offset
    prefix="/informeContable",
)

informe_contable_router = factory.get_router()


@informe_contable_router.patch("/update_id_carga/{id}")
async def update_id_carga(
    id: str,
    payload: InformeContableUpdateIdCarga,
    service: InformeContableServiceDependency,
):
    return await service.update_id_carga(id=id, id_carga=payload.id_carga)
