# Droguería Caribe · POS con Factus Pay y Facturación Electrónica

Punto de venta web para una droguería que **cobra con Factus Pay** (QR o llave Bre-B) y **emite la factura electrónica DIAN con Factus Facturación** en cuanto el pago se confirma, sin que el cajero tenga que hacer nada más.

Proyecto del **Reto Factus: De Facturación y Recaudos** (hackatón). Funciona en el **ambiente sandbox** de Factus: no se procesa dinero real.

- **Demo desplegada:** https://drogueriacaribe-a-production.up.railway.app/tienda
- **Documentación de la API (Swagger):** https://drogueriacaribe-a-production.up.railway.app/docs
- **Arquitectura detallada y diagramas:** [ARQUITECTURA.md](ARQUITECTURA.md)

---

## Integrantes

| Nombre | Rol |
|---|---|
| _Nombre completo_ | _Backend / Factus Facturación_ |
| _Nombre completo_ | _Backend / Factus Pay_ |
| _Nombre completo_ | _Frontend_ |
| _Nombre completo_ | _Infraestructura, despliegue y documentación_ |

---

## El problema

En una droguería pequeña, cobrar y facturar son dos tareas separadas: el cajero recibe una transferencia, la revisa en el celular y después abre otro sistema para emitir la factura. Eso genera filas, errores de digitación, pagos sin factura y facturas sin pago, y la conciliación se hace a mano al final del día.

## La solución

Un solo flujo, de punta a punta:

1. El cliente arma su carrito y escribe su NIT, nombre y correo.
2. El sistema crea un **recaudo en Factus Pay** y muestra el **QR** (y la llave Bre-B) por el valor exacto de la compra, IVA incluido.
3. El cliente paga desde su banco (en sandbox, desde el simulador de Factus Pay).
4. Factus Pay avisa por **webhook** (o el sistema lo detecta por **polling**), y el backend confirma el pago, descuenta el inventario y **emite la factura electrónica** con Factus Facturación.
5. La pantalla muestra la factura validada: número, **CUFE** y enlace al PDF.

El pago y la factura comparten el mismo **código de referencia** (`TRX-AAAAMMDD-XXXX`), así que cada factura queda asociada automáticamente al dinero recaudado: **trazabilidad y conciliación sin trabajo manual**.

---

## Flujo (Opción A del reto: cobro previo)

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant T as Tienda (/tienda)
    participant B as Backend FastAPI
    participant P as Factus Pay
    participant F as Factus Facturación
    participant DB as PostgreSQL

    C->>T: Carrito + NIT, nombre y correo
    T->>B: POST /api/ventas
    B->>DB: Venta PENDIENTE_PAGO
    B->>P: POST /v1/collections (reference_code, amount, expiration)
    P-->>B: QR + llave Bre-B
    B-->>T: QR, referencia y total
    C->>P: Paga el QR (simulador sandbox)
    alt Webhook (app desplegada)
        P->>B: POST /webhook/factus-pay?key=LLAVE
    else Polling (cada 3 s desde la tienda)
        T->>B: GET /api/ventas/{ref}/poll
        B->>P: GET /v1/collections/{ref}
    end
    B->>DB: Venta PAGADA, descuenta stock
    B->>F: POST /v2/bills/validate (misma referencia)
    F-->>B: Número, CUFE, enlaces
    B->>DB: Venta FACTURADA
    T->>B: GET /api/ventas/{ref}/poll
    B-->>T: Factura, CUFE y enlace al PDF
```

Estados de una venta: `PENDIENTE_PAGO` → `PAGADA` → `FACTURADA`. Si Factus rechaza la factura, la venta queda en `ERROR_FACTURACION` con el mensaje de error guardado, y el pago no se pierde.

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async, asyncpg), Pydantic v2, httpx |
| Base de datos | PostgreSQL 16 (Docker) |
| Frontend | HTML + Tailwind CSS + JavaScript, servido por el backend en `/tienda` |
| APIs externas | Factus Pay (recaudos) y Factus Facturación v2 (factura electrónica DIAN) |
| Despliegue | Docker + Railway |

## Estructura del repositorio

```text
.
├── docker-compose.yml        # PostgreSQL + backend
├── .env.example              # Variables con valores de ejemplo (nunca credenciales reales)
├── ARQUITECTURA.md           # Arquitectura, diagramas y endpoints de Factus
├── frontend/                 # Catálogo web (index.html, catalog.js, cart.js)
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── tests/                # pytest
    └── app/
        ├── main.py           # App FastAPI, rutas /health, /tienda y webhook
        ├── core/config.py    # Variables de entorno (pydantic-settings)
        ├── api/              # Rutas: ventas, productos, clientes, recaudos (webhook)
        ├── db/               # Modelos SQLAlchemy y seed de productos
        ├── schemas/          # Esquemas Pydantic de entrada y salida
        ├── services/
        │   ├── factus_pay.py     # Cliente de Factus Pay (auth, recaudos)
        │   ├── factus_bill.py    # Cliente de Factus Facturación (token, validar, PDF)
        │   ├── facturacion.py    # Arma la factura y la emite
        │   └── ventas.py         # Confirma el pago, descuenta stock, dispara la factura
        └── static/tienda.html    # Tienda web con el flujo completo
```

---

## Cómo correrlo en local

**Requisitos:** Docker con Docker Compose y credenciales del sandbox de Factus (Pay y Facturación).

1. Clonar el repositorio y crear el `.env`:
   ```bash
   git clone https://github.com/HiroUzu1/Drogueria_Caribe-a.git
   cd Drogueria_Caribe-a
   cp .env.example .env
   ```
2. Llenar en `.env` las credenciales de Factus (ver [Variables de entorno](#variables-de-entorno)).
3. Levantar la base de datos y el backend:
   ```bash
   docker compose up -d --build
   ```
4. Cargar los productos de ejemplo:
   ```bash
   docker compose exec backend python -m app.db.seed_productos
   ```
5. Abrir:
   - Tienda: http://localhost:8000/tienda
   - Swagger: http://localhost:8000/docs
   - Salud: http://localhost:8000/health

En local el webhook de Factus Pay no puede llegar (necesita una URL pública HTTPS); el pago se confirma igual por **polling**, porque la tienda consulta el estado cada 3 segundos.

### Tests

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest -q
```

---

## Variables de entorno

Todas están en [`.env.example`](.env.example) con valores de ejemplo. **El `.env` real nunca se sube al repositorio** (está en `.gitignore`).

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL con el driver async: `postgresql+asyncpg://usuario:clave@host:puerto/base` |
| `FACTUS_PAY_BASE_URL` | `https://pay-api-sandbox.factus.com.co` |
| `FACTUS_PAY_EMAIL` / `FACTUS_PAY_PASSWORD` | Credenciales de Factus Pay (login con email y contraseña) |
| `FACTUS_PAY_WEBHOOK_KEY` | Llave secreta del webhook; debe ser la misma configurada en el panel de Factus Pay |
| `FACTUS_PAY_QR_EXPIRATION_SECONDS` | Vigencia del QR en segundos (por defecto 1800) |
| `FACTUS_PAY_POLL_ENABLED` | `true` para confirmar pagos consultando a Factus cuando no llega el webhook |
| `FACTUS_BILL_BASE_URL` | `https://api-sandbox.factus.com.co` |
| `FACTUS_BILL_CLIENT_ID` / `FACTUS_BILL_CLIENT_SECRET` | Credenciales OAuth de Factus Facturación |
| `FACTUS_BILL_USERNAME` / `FACTUS_BILL_PASSWORD` | Usuario y contraseña de Factus Facturación |
| `FACTUS_NUMBERING_RANGE_ID` | Rango de numeración de facturas (en el sandbox: `389`, prefijo `SETP`) |
| `FACTUS_DEFAULT_MUNICIPALITY_ID` | Municipio de respaldo si el cliente no tiene uno |
| `ADMIN_API_KEY` | Llave para los endpoints de administración (header `X-Admin-Key`) |

---

## Endpoints de nuestra API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/tienda` | Tienda web: carrito, cobro con QR y factura |
| `GET` | `/api/productos` | Productos con stock disponible |
| `GET` | `/api/productos/{code_reference}` | Un producto por su código |
| `POST` | `/api/ventas` | Crea la venta y el recaudo en Factus Pay; devuelve el QR |
| `GET` | `/api/ventas/{reference_code}/estado` | Estado de la venta (con `?refresh=true` consulta también a Factus Pay) |
| `GET` | `/api/ventas/{reference_code}/poll` | Consulta a Factus Pay y devuelve el estado, la factura y el CUFE |
| `POST` | `/webhook/factus-pay?key=...` | Webhook de Factus Pay (también en `/api/webhook/factus-pay`) |
| `GET` | `/api/clientes/{identificacion}` | Busca un cliente |
| `POST` | `/api/clientes` | Registra un cliente |
| `GET` | `/health` | Estado del servicio |

**Ejemplo para crear una venta:**

```bash
curl -X POST http://localhost:8000/api/ventas \
  -H "Content-Type: application/json" \
  -d '{
    "identificacion": "900123456",
    "nombres": "Cliente",
    "apellidos": "Prueba",
    "email": "cliente@example.com",
    "items": [{
      "producto_id": "<id de GET /api/productos>",
      "code_reference": "DICLO-50",
      "name": "Diclofenaco 50mg",
      "quantity": 2,
      "price": 8000,
      "tax_amount": 800,
      "unit_measure_code": "94",
      "standard_code": "999",
      "taxes": "[{\"code\":\"01\",\"rate\":\"5.00\"}]"
    }]
  }'
```

---

## Integración con las APIs de Factus

### Factus Pay (recaudo)

| Uso | Endpoint de Factus |
|---|---|
| Autenticación (email y contraseña, devuelve un token) | `POST /auth` |
| Crear el recaudo con QR y llave Bre-B | `POST /v1/collections` |
| Consultar el estado del pago (polling) | `GET /v1/collections/{reference_code}` |
| Notificación de pago | Webhook `POST /webhook/factus-pay?key=LLAVE` |

- El `reference_code` del recaudo es el mismo de la venta y de la factura.
- **Webhook:** se valida la llave con comparación de tiempo constante (401 si no coincide), se confirma que el monto coincida con la venta y se procesa una sola vez aunque llegue repetido. La factura se emite en segundo plano para responder a Factus en menos de 10 segundos.
- Factus Pay permite **un solo token activo por usuario**: cada login invalida el anterior.

### Factus Facturación (factura electrónica DIAN, API v2)

| Uso | Endpoint de Factus |
|---|---|
| Token OAuth2 (password grant, dura 1 hora) | `POST /oauth/token` |
| Crear y validar la factura ante la DIAN | `POST /v2/bills/validate` |
| Eliminar una factura pendiente (si Factus responde 409) | `DELETE /v2/bills/destroy/reference/{reference_code}` |
| Descargar PDF y XML | `GET /v2/bills/{number}/download-pdf`, `/download-xml` |

- Forma de pago `1` (contado) y medio de pago `47` (transferencia), con la referencia del recaudo.
- Productos con IVA (`[{"code":"01","rate":"5.00"}]`) o excluidos (`[{"is_excluded": true}]`).
- Si Factus responde **409** (factura pendiente con la misma referencia), se elimina y se reintenta una vez.
- Si la factura falla, se guarda el error y la venta queda en `ERROR_FACTURACION`; el pago no se pierde.

**Factura en sandbox:** Factus no envía correos en el ambiente de pruebas, así que la factura se muestra en la tienda (número, CUFE y enlace al PDF). En producción, Factus la envía automáticamente al correo del cliente.

---

## Despliegue (Railway)

1. Servicio desde este repositorio, rama `main`, con **Root Directory `/backend`** (usa `backend/Dockerfile`).
2. Servicio de PostgreSQL. La `DATABASE_URL` del backend usa las variables de Railway:
   ```text
   postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
   ```
3. Las demás variables de entorno se configuran en el panel de Railway (nunca en archivos del repositorio), con `PORT=8000`.
4. Dominio público con HTTPS en el puerto 8000.
5. En el panel de Factus Pay, el webhook apunta a `https://<dominio>/webhook/factus-pay` con la misma llave de `FACTUS_PAY_WEBHOOK_KEY`.
6. Las tablas se crean solas al arrancar; los productos se cargan con `python -m app.db.seed_productos`.

Cada push a `main` despliega automáticamente.

---

## Cómo probar la demo

1. Abrir https://drogueriacaribe-a-production.up.railway.app/tienda
2. Agregar productos al carrito (el sandbox de Factus Pay pide un total de **al menos $10.000**).
3. Escribir un NIT de prueba (por ejemplo `900123456`, **sin dígito de verificación**), un nombre y un correo.
4. Pagar el QR en el simulador: https://pay-api-sandbox.factus.com.co/simulator
5. En unos segundos la tienda muestra la factura validada con su número, CUFE y enlace al PDF.

---

## Seguridad

- Ninguna credencial real en el repositorio: el `.env` está en `.gitignore` y `.env.example` solo tiene valores de ejemplo.
- En producción, las credenciales viven en las variables de entorno de Railway.
- El webhook valida la llave secreta con comparación de tiempo constante y rechaza toda petición si la llave no está configurada.
- Antes de marcar una venta como pagada, se verifica que el monto pagado coincida con el total.
- Solo se usan los ambientes **sandbox** de Factus, como exige el reto.
