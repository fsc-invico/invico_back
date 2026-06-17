from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlBancoCruzadoDocument,
    ControlBancoCruzadoFullFilter,
    ControlBancoCruzadoLiteFilter,
)
from ..services import ControlBancoCruzadoService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ControlBancoCruzadoService,
    report_schema=ControlBancoCruzadoDocument,
    full_filter_schema=ControlBancoCruzadoFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlBancoCruzadoLiteFilter,  # No usa limit/offset
    prefix="/controlBanco/cruzado",
)

control_banco_cruzado_router = factory.get_router()
