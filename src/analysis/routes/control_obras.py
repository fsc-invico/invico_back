from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlObrasDocument,
    ControlObrasFullFilter,
    ControlObrasLiteFilter,
)
from ..services import ControlObrasService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ControlObrasService,
    report_schema=ControlObrasDocument,
    full_filter_schema=ControlObrasFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlObrasLiteFilter,  # No usa limit/offset
    prefix="/controlObras",
)

control_obras_router = factory.get_router()
