from typing import Union, Optional


def decimal(value: Union[str, float] = None) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 2)


def integer(value: Union[str, int] = None) -> Optional[int]:
    if value is None:
        return None
    return int(value)
