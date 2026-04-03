__all__ = ["BaseFilterParams", "apply_auto_filter", "parse_filter_keys"]

from typing import Literal, Optional

from bson import ObjectId
from pydantic import Field, PrivateAttr

from .alias_generator import CamelModel

op_map = {
    ">=": "$gte",
    "<=": "$lte",
    "!=": "$ne",
    ">": "$gt",
    "<": "$lt",
    "=": "$eq",
    "~": "$regex",
}


# -------------------------------------------------
def data_filter(
    filter_params: str,
    get_deleted: Optional[bool] = None,
    extra_filter: Optional[dict] = None,
):
    filter_dict = {}
    filter_item_list = filter_params.split(",")

    for filter_item in filter_item_list:
        filter_dict.update(get_filter_query(filter_item))

    if get_deleted:
        filter_dict.update(
            deactivated_at={"$ne": None} if get_deleted else {"$eq": None}
        )

    if extra_filter:
        filter_dict.update(extra_filter)

    return filter_dict


# -------------------------------------------------
def get_filter_query(f):
    op = ""
    for o in op_map:
        if o in f:
            op = o
            break
    if not op:
        return {}

    k, v = f.split(op)
    return {k.strip(): {op_map[op]: format_value(v)}}


# # -------------------------------------------------
# def format_value(v):
#     return (
#         int(v)
#         if v.strip().isdigit()
#         else (
#             float(v)
#             if v.strip().isdecimal()
#             else ObjectId(v.strip())
#             if len(v.strip()) == 24
#             else v.strip()
#         )
#     )


# -------------------------------------------------
def format_value(v: str):
    v = v.strip()

    # Forzar string con prefijo "str:", por ejemplo fuente=str:10
    if v.startswith("str:"):
        return v[4:]

    # Forzar número con prefijo "num:"
    if v.startswith("num:"):
        return int(v[4:]) if v[4:].isdigit() else float(v[4:])

    # Intento automático
    if v.isdigit():
        return int(v)
    if len(v) == 24:
        try:
            return ObjectId(v)
        except Exception:
            pass
    return v


# -------------------------------------------------
class BaseFilterParams(CamelModel):
    query_filter: str = ""
    # limit: int = Field(20, gt=0, le=100)
    # Si limit es None, el repositorio debería traer TODO
    limit: Optional[int] = Field(100, gte=0)
    offset: int = Field(0, ge=0)
    sort_by: str = "_id"
    sort_dir: Literal["asc", "desc"] = "asc"

    # Campo interno, no forma parte de la query
    _extra_filter: dict = PrivateAttr(default_factory=dict)

    def set_extra_filter(self, extra: Optional[dict]):
        if extra:
            self._extra_filter.update(extra)

    def get_full_filter(self):
        # return data_filter(self.query_filter, extra_filter=self._extra_filter)
        """
        Genera el diccionario final para MongoDB combinando la query_filter string
        con los campos adicionales definidos en las clases hijas.
        """
        # 1. Detectar campos adicionales en la clase hija
        base_fields = set(BaseFilterParams.model_fields.keys())
        current_fields = set(type(self).model_fields.keys())
        additional_fields = current_fields - base_fields

        # 2. Agregar automáticamente esos campos al extra_filter
        for field in additional_fields:
            value = getattr(self, field, None)
            if value is not None:
                # Si es un Enum o tiene atributo 'value', lo extraemos
                val = value.value if hasattr(value, "value") else value
                if isinstance(val, str) and "," in val:
                    elementos = [x.strip() for x in val.split(",")]
                    # Intentamos convertir a int, si no se puede, queda como str
                    lista_final = []
                    for e in elementos:
                        try:
                            lista_final.append(int(e))
                        except ValueError:
                            lista_final.append(e)
                    self._extra_filter.update({field: {"$in": lista_final}})
                else:
                    try:
                        val = int(
                            val
                        )  # PUEDE ROMPER SI ERA STRING QUE SE VEÍA COMO INT
                    except ValueError:
                        pass
                    self._extra_filter.update({field: {"$eq": val}})

        # 3. Combinar con la lógica de data_filter (la que parsea el string)
        return data_filter(self.query_filter, extra_filter=self._extra_filter)


# -------------------------------------------------
def apply_auto_filter(params: BaseFilterParams) -> None:
    base_fields = set(BaseFilterParams.model_fields.keys())
    param_fields = set(type(params).model_fields.keys())

    # Detectamos sólo los campos nuevos del modelo hijo
    additional_fields = param_fields - base_fields

    for field in additional_fields:
        value = getattr(params, field, None)
        if value is not None:
            params.set_extra_filter(
                {field: {"$eq": value.value if hasattr(value, "value") else value}}
            )


# -------------------------------------------------
def parse_filter_keys(filters: dict) -> dict:
    """
    Convierte claves tipo 'campo__operador' en filtros MongoDB.
    Ej: {"edad__gt": 30} => {"edad": {"$gt": 30}}
    """
    mongo_filters = {}
    for key, value in filters.items():
        if "__" in key:
            field, op = key.split("__", 1)
            mongo_filters.setdefault(field, {})[f"${op}"] = value
        else:
            mongo_filters[key] = value
    return mongo_filters
