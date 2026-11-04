def construir_payload_dian(transaccion, cliente, items_transaccion) -> dict:
    """Transforma una transacción de la BD al JSON requerido por Factus Bill (DIAN)."""
    
    # 1. Armar nombre completo del cliente
    nombre_completo = f"{cliente.nombres or ''} {cliente.apellidos or ''}".strip()
    if not nombre_completo:
        nombre_completo = "CONSUMIDOR FINAL"

    # 2. Transformar ítems del carrito
    items_dian = []
    for item in items_transaccion:
        items_dian.append({
            "code_reference": item.code_reference,
            "name": item.name,
            "quantity": item.quantity,
            "discount_rate": 0,
            "price": float(item.price),
            "tax_rate": f"{float(item.tax_rate):.2f}",
            "unit_measure_id": 94,  # Código 94 = Unidad
            "standard_code_id": 1,
            "is_excluded": 1 if float(item.tax_rate) == 0 else 0
        })

    # 3. Construir estructura completa
    return {
        "numbering_range_id": 1,
        "reference_code": transaccion.reference_code,
        "observation": "Factura emitida desde Droguería Caribe POS",
        "payment_form": "1",          # Contado
        "payment_method_code": "47",  # Transferencia / Pasarela Factus Pay
        "customer": {
            "identification": cliente.identificacion,
            "names": nombre_completo,
            "email": cliente.email,
            "phone": cliente.telefono or "3000000000",
            "address": getattr(cliente, "direccion", None) or "Montería, Córdoba",
            "legal_organization_id": "2",  # Persona Natural
            "tribute_id": "21",            # No aplica
            "identification_document_id": "3" # Cédula
        },
        "items": items_dian
    }