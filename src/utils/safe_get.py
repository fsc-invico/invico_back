__all__ = ["sanitize_dataframe_for_json", "sanitize_dataframe_for_json_with_datetime"]

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


# -------------------------------------------------
def _is_null_value(value: Any) -> bool:
    """Detecta nulls de cualquier dtype sin la ambigüedad de ``pd.isna``.

    ``pd.isna`` devuelve arrays ante listas/dicts y revuelve un
    ``ValueError`` dentro de un ``if``; acá solo se evalúan escalares.

    Args:
        value: Valor de la celda a evaluar.

    Returns:
        ``True`` si el valor representa un null (None, pd.NA, pd.NaT,
        NaN, Decimal NaN o np.datetime64 NaT).
    """
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    # np.float64 hereda de float, así que cubre ambos
    if isinstance(value, (float, np.floating)):
        return math.isnan(value)
    if isinstance(value, Decimal):
        return value.is_nan()
    if isinstance(value, np.datetime64):
        return bool(np.isnat(value))
    return False


# -------------------------------------------------
def _to_json_safe_value(value: Any, convert_dates: bool) -> Any:
    """Convierte una celda en un valor seguro para ``json.dumps(allow_nan=False)``.

    Reglas:
    - ``None`` / ``pd.NA`` / ``pd.NaT`` / ``NaN`` / ±``inf`` -> ``None``.
    - ``Decimal`` no finito -> ``None``; finito -> ``float``.
    - Escalares numpy (``np.int64``, ``np.bool_``, ``np.datetime64``...)
      -> equivalentes nativos de Python.
    - Fechas (``pd.Timestamp`` / ``datetime`` / ``date``) -> ``dd/mm/aaaa``
      sólo cuando ``convert_dates`` es ``True``.

    Args:
        value: Valor de la celda a convertir.
        convert_dates: Si ``True``, formatea fechas como ``dd/mm/aaaa``.

    Returns:
        El valor convertido (serializable a JSON).
    """
    if _is_null_value(value):
        return None
    if isinstance(value, (float, np.floating)):
        # NaN/±inf -> None; los finitos se homogeneizan a float de Python
        return float(value) if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else None
    if isinstance(value, np.datetime64):
        # pd.Timestamp evita el OverflowError de .item() con resolución ns
        value = pd.Timestamp(value).to_pydatetime()
    elif isinstance(value, np.generic):
        value = value.item()
        if _is_null_value(value):
            return None
    if convert_dates and isinstance(value, (pd.Timestamp, datetime, date)):
        return value.strftime("%d/%m/%Y")
    return value


# -------------------------------------------------
def _sanitize_dataframe(df: pd.DataFrame, convert_dates: bool) -> pd.DataFrame:
    """Núcleo compartido por los dos sanitizadores públicos.

    Con pandas 3.x ``DataFrame.apply`` / ``DataFrame.map`` re-infiere los
    dtypes de las columnas ``object`` (a ``float64`` o
    ``StringDtype(na_value=nan)``) y revierte los ``None`` a ``NaN``. Por
    eso el último paso es siempre ``astype(object).where(notnull, None)``:
    al no haber ninguna inferencia posterior, las celdas nulas quedan como
    ``None`` (JSON ``null``) y no como ``nan``.

    Args:
        df: DataFrame a sanitizar.
        convert_dates: Si ``True``, formatea fechas como ``dd/mm/aaaa``.

    Returns:
        DataFrame con celdas ``None``/nativas, sin ``nan`` ni ``inf``.
        Los DataFrames vacíos se devuelven tal cual.
    """
    if df.empty:
        return df

    for col in ["_id", "id"]:
        if col in df.columns:
            # Convertimos a string solo si la columna tiene objetos tipo ObjectId
            df[col] = df[col].astype(str)

    # 1️⃣ Normalización celda a celda en un solo pase (sin inferencia de dtypes)
    values = df.astype(object).to_numpy()
    converted = [
        [_to_json_safe_value(cell, convert_dates) for cell in row] for row in values
    ]

    # 2️⃣ PASO FINAL OBLIGATORIO: aquí ya no se infiere nada más, así que
    #    los None sobreviven (mata el 'Out of range float values are not
    #    JSON compliant: nan' de la subida a Google Sheets).
    df_clean = pd.DataFrame(converted, index=df.index, columns=df.columns)
    return df_clean.astype(object).where(pd.notnull(df_clean), None)


# -------------------------------------------------
def sanitize_dataframe_for_json(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia un DataFrame para que sea seguro convertirlo a JSON, MongoDB o para validación con Pydantic.

    - Reemplaza np.nan, np.inf, -np.inf, NaT y pd.NA con None
    - Convierte np.* types a tipos nativos de Python

    Args:
        df: DataFrame a sanitizar (las fechas se conservan como objetos).

    Returns:
        DataFrame con celdas ``None``/nativas, sin ``nan`` ni ``inf``.
    """
    return _sanitize_dataframe(df, convert_dates=False)


# -------------------------------------------------
def sanitize_dataframe_for_json_with_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia un DataFrame para que sea seguro convertirlo a JSON o subirlo a Google Sheets.

    Reemplaza:
    - np.nan, np.inf, -np.inf, NaT y pd.NA con None
    - np.* types con sus equivalentes nativos
    - Fechas (Timestamp/datetime/date) con texto ``dd/mm/aaaa``

    Args:
        df: DataFrame a sanitizar.

    Returns:
        DataFrame con celdas ``None``/nativas, sin ``nan`` ni ``inf``.
    """
    return _sanitize_dataframe(df, convert_dates=True)
