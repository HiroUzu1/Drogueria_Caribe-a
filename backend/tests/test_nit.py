import pytest

from app.services.nit import dv_for, parse_nit


def test_valid_nit_with_dv():
    number = "900373913"
    dv = dv_for(number)
    assert parse_nit(f"{number}-{dv}") == (number, str(dv))
    assert parse_nit(f" 900.373.913 - {dv} ") == (number, str(dv))


def test_wrong_dv_rejected():
    number = "900373913"
    wrong = (dv_for(number) + 1) % 10
    with pytest.raises(ValueError):
        parse_nit(f"{number}-{wrong}")


@pytest.mark.parametrize("value", ["1", "abc", "abc9003739134", "12345678901234567"])
def test_malformed_nit_rejected(value):
    with pytest.raises(ValueError):
        parse_nit(value)
