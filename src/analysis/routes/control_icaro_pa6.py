from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlIcaroPA6Document,
    ControlIcaroPA6FullFilter,
    ControlIcaroPA6LiteFilter,
)
from ..services import ControlIcaroPA6Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ControlIcaroPA6Service,
    report_schema=ControlIcaroPA6Document,
    full_filter_schema=ControlIcaroPA6FullFilter,  # Usa limit/offset
    lite_filter_schema=ControlIcaroPA6LiteFilter,  # No usa limit/offset
    prefix="/controlIcaro/pa6",
)

control_icaro_pa6_router = factory.get_router()
