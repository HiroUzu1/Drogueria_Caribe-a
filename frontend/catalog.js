/**
 * catalog.js - Carga y renderizado del catálogo desde el Backend FastAPI.
 */

// URL base de tu API en FastAPI
const API_BASE_URL = window.location.origin.includes('localhost')
    ? 'http://localhost:8000'
    : '';

// Productos de respaldo en caso de que el backend FastAPI no esté corriendo
const MOCK_PRODUCTS = [
    {
        id: "prod-001",
        code_reference: "MED-001",
        name: "Protector Solar FPS 50+ Caribe",
        description: "Alta protección contra rayos UVA/UVB resistente al sudor costero.",
        price: 45000,
        iva_excluido: false,
        tax_rate: 19.00,
        category: "Cuidado Personal",
        badge: "Más Vendido",
        image: "https://images.unsplash.com/photo-1598440947619-2c35fc9aa908?auto=format&fit=crop&w=400&q=80"
    },
    {
        id: "prod-002",
        code_reference: "MED-002",
        name: "Dolex Forte 500mg (Caja x 16)",
        description: "Alivio rápido y efectivo para dolores de cabeza y fiebre.",
        price: 12500,
        iva_excluido: true,
        tax_rate: 0,
        category: "Medicamentos",
        badge: "Venta Libre",
        image: "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=400&q=80"
    },
    {
        id: "prod-003",
        code_reference: "MED-003",
        name: "Pedialyte MAX Electrolitos 500ml",
        description: "Rehidratación oral rápida ideal para clima cálido.",
        price: 9800,
        iva_excluido: true,
        tax_rate: 0,
        category: "Hidratación",
        badge: "Recomendado",
        image: "https://images.unsplash.com/photo-1527613426441-4da17471b66d?auto=format&fit=crop&w=400&q=80"
    },
    {
        id: "prod-004",
        code_reference: "MED-004",
        name: "Vitamina C + Zinc 1000mg",
        description: "Suplemento efervescente para fortalecer el sistema inmune.",
        price: 28000,
        iva_excluido: true,
        tax_rate: 0,
        category: "Nutrición",
        badge: "Oferta",
        image: "https://images.unsplash.com/photo-1577401239170-897942555fb3?auto=format&fit=crop&w=400&q=80"
    }
];

/**
 * Obtiene los productos desde FastAPI (/api/productos)
 */
async function fetchProductsFromBackend() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/productos`);
        if (!response.ok) {
            throw new Error(`Error en servidor: ${response.status}`);
        }
        const data = await response.json();
        // Si el backend responde con { items: [...] } o un array directo
        return data.items || data;
    } catch (error) {
        console.warn('⚠️ No se pudo conectar con FastAPI (/api/productos). Usando datos Mock locales:', error);
        return MOCK_PRODUCTS;
    }
}

/**
 * Formateador de moneda en pesos colombianos (COP)
 */
function formatCOP(amount) {
    return new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        maximumFractionDigits: 0
    }).format(amount);
}

/**
 * Renderiza los productos dentro del elemento HTML #product-grid
 */
async function renderCatalog() {
    const gridContainer = document.getElementById('product-grid');
    if (!gridContainer) return;

    // Estado de carga visual
    gridContainer.innerHTML = `
        <div class="col-span-full text-center py-12 text-teal-700">
            <svg class="animate-spin h-8 w-8 mx-auto mb-3 text-orange-500" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
            </svg>
            <p class="font-medium">Cargando productos de Droguería Caribeña...</p>
        </div>
    `;

    const products = await fetchProductsFromBackend();

    if (products.length === 0) {
        gridContainer.innerHTML = `<p class="col-span-full text-center text-gray-500">No hay productos disponibles.</p>`;
        return;
    }

    gridContainer.innerHTML = products.map(prod => `
        <div class="bg-white rounded-2xl shadow-sm hover:shadow-md transition border border-teal-100/60 overflow-hidden flex flex-col justify-between">
            <div>
                <div class="relative h-48 bg-gray-100">
                    <img src="${prod.image || 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=400&q=80'}" 
                         alt="${prod.name}" 
                         class="w-full h-full object-cover">
                    <span class="absolute top-3 right-3 bg-teal-600 text-white text-xs px-2.5 py-1 rounded-full font-bold shadow-sm">
                        ${prod.badge || (prod.iva_excluido ? 'Venta Libre' : '19% IVA')}
                    </span>
                </div>
                <div class="p-5">
                    <span class="text-xs font-semibold text-teal-600 uppercase tracking-wider">${prod.category || 'Farmacia'}</span>
                    <h3 class="font-bold text-gray-800 text-lg mt-1 mb-2">${prod.name}</h3>
                    <p class="text-gray-600 text-sm mb-4 line-clamp-2">${prod.description || ''}</p>
                </div>
            </div>
            
            <div class="p-5 pt-0 flex items-center justify-between border-t border-gray-50 mt-auto">
                <div>
                    <span class="text-xs text-gray-600 block">Precio final</span>
                    <span class="text-xl font-black text-teal-900">${formatCOP(prod.price)}</span>
                </div>
                <button onclick="Cart.addItem(${JSON.stringify(prod).replace(/"/g, '&quot;')})" 
                        class="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2.5 rounded-xl font-semibold flex items-center gap-2 transition shadow-md shadow-orange-500/20 active:scale-95">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                    </svg>
                    Añadir
                </button>
            </div>
        </div>
    `).join('');
}

// Inicializar el catálogo al cargar el DOM
document.addEventListener('DOMContentLoaded', renderCatalog);