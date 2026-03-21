def get_quantity_kind(series, col_name, quantity_kinds=None):
    """
    Resolve quantity kind for a pandas Series column.

    Priority:
      1. Explicit quantity_kinds dict entry
      2. Pint unit from dtype (unit string IS the quantity kind)
      3. Column name
    """
    if quantity_kinds and col_name in quantity_kinds:
        return quantity_kinds[col_name]

    try:
        import pint_pandas  # noqa: F401
        if hasattr(series.dtype, "units"):
            return str(series.dtype.units)
    except ImportError:
        pass

    return col_name


def to_float32(series):
    """Extract a float32 numpy array from a pandas Series, stripping Pint units if present."""
    import numpy as np

    try:
        import pint_pandas  # noqa: F401
        if hasattr(series.dtype, "units"):
            return np.asarray(series.pint.magnitude, dtype=np.float32)
    except ImportError:
        pass

    return np.asarray(series.values, dtype=np.float32)
