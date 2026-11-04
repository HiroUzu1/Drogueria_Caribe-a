from decimal import Decimal
from types import SimpleNamespace

from app.services.facturacion import construir_factura, impuestos_linea


def test_iva_excluido_no_suma_impuesto():
    iva, taxes = impuestos_linea(Decimal("10000"), 3, True, Decimal("19"))
    assert iva == Decimal("0.00")
    assert '"is_excluded": true' in taxes


def test_iva_19_por_ciento():
    iva, taxes = impuestos_linea(Decimal("25000"), 2, False, Decimal("19"))
    assert iva == Decimal("9500.00")
    assert '"rate": "19.00"' in taxes


def test_construir_factura_contado_transferencia():
    item = SimpleNamespace(
        code_reference="SKU1", name="Acetaminofén", quantity=2, price=Decimal("10000"),
        unit_measure_code="94", standard_code="999", taxes='[{"is_excluded": true}]',
    )
    cliente = SimpleNamespace(
        identificacion="900373913", dv="4", razon_social="Cliente SAS",
        email="c@example.com", municipio_code=None,
    )
    tx = SimpleNamespace(
        reference_code="DC-1", observacion=None, total=Decimal("20000"),
        cliente=cliente, items=[item],
    )
    bill = construir_factura(tx)
    assert bill["operation_type"] == 10
    assert bill["payment_details"][0]["payment_method_code"] == 47
    assert bill["payment_details"][0]["amount"] == 20000.0
    assert bill["items"][0]["taxes"] == [{"is_excluded": True}]
    assert bill["customer"]["identification"] == "900373913"
