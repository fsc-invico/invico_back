from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlIcaroAnualDocument,
    ControlIcaroAnualFullFilter,
    ControlIcaroAnualLiteFilter,
)
from ..services import ControlIcaroAnualService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ControlIcaroAnualService,
    report_schema=ControlIcaroAnualDocument,
    full_filter_schema=ControlIcaroAnualFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlIcaroAnualLiteFilter,  # No usa limit/offset
    prefix="/controlIcaro/anual",
)

control_icaro_anual_router = factory.get_router()
