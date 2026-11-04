"""Validación de NIT colombiano (formato y dígito de verificación, sin consultar DIAN)."""

import re

_WEIGHTS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def dv_for(number: str) -> int:
    total = sum(int(d) * w for d, w in zip(reversed(number), _WEIGHTS))
    remainder = total % 11
    return remainder if remainder <= 1 else 11 - remainder


def parse_nit(value: str) -> tuple[str, str]:
    """Devuelve (numero, dv). Exige el dígito de verificación al final."""
    if not re.fullmatch(r"[0-9.\-\s]+", value):
        raise ValueError("El NIT solo puede contener dígitos, puntos, espacios y guiones.")
    digits = re.sub(r"\D", "", value)
    if not 6 <= len(digits) <= 16:
        raise ValueError("El NIT debe tener entre 5 y 15 dígitos más el dígito de verificación.")
    number, dv = digits[:-1], digits[-1]
    if int(dv) != dv_for(number):
        raise ValueError("El dígito de verificación del NIT no es válido.")
    return number, dv
