/**
 * cart.js - Administración del estado del Carrito compartido vía localStorage.
 */

const Cart = {
    STORAGE_KEY: 'drogueria_caribena_cart',

    /**
     * Obtiene los productos almacenados en el localStorage (Equivalente a leer un JSON en disk)
     */
    getItems() {
        try {
            return JSON.parse(localStorage.getItem(this.STORAGE_KEY)) || [];
        } catch (e) {
            console.error('Error al leer el carrito de localStorage:', e);
            return [];
        }
    },

    /**
     * Guarda la lista de productos actual en localStorage
     */
    saveItems(items) {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(items));
        this.render();
    },

    /**
     * Agrega un producto o incrementa su cantidad
     */
    addItem(product) {
        const items = this.getItems();
        const index = items.findIndex(item => item.id === product.id);

        if (index > -1) {
            items[index].quantity += 1;
        } else {
            items.push({
                id: product.id,
                code_reference: product.code_reference,
                name: product.name,
                price: product.price,
                iva_excluido: product.iva_excluido,
                image: product.image,
                quantity: 1
            });
        }

        this.saveItems(items);
        this.openDrawer();
        this.showToast(`¡${product.name} agregado!`);
    },

    /**
     * Modifica la cantidad de un ítem (+1 o -1)
     */
    updateQuantity(productId, delta) {
        let items = this.getItems();
        const item = items.find(i => i.id === productId);

        if (item) {
            item.quantity += delta;
            if (item.quantity <= 0) {
                items = items.filter(i => i.id !== productId);
            }
        }
        this.saveItems(items);
    },

    /**
     * Elimina completamente un producto del carrito
     */
    removeItem(productId) {
        const items = this.getItems().filter(i => i.id !== productId);
        this.saveItems(items);
    },

    /**
     * Vacía el carrito por completo (Ej: al terminar una venta exitosa)
     */
    clear() {
        localStorage.removeItem(this.STORAGE_KEY);
        this.render();
    },

    /**
     * Calcula el subtotal general de la compra
     */
    getSubtotal() {
        return this.getItems().reduce((sum, item) => sum + (item.price * item.quantity), 0);
    },

    /**
     * Retorna la cantidad total de unidades en el carrito
     */
    getTotalCount() {
        return this.getItems().reduce((sum, item) => sum + item.quantity, 0);
    },

    /**
     * Renderiza los componentes visuales del carrito (Badge superior, lista lateral y totales)
     */
    render() {
        const items = this.getItems();
        const subtotal = this.getSubtotal();
        const totalCount = this.getTotalCount();

        // 1. Actualizar Badge del Header
        const badge = document.getElementById('cart-count');
        if (badge) {
            badge.textContent = totalCount;
            badge.classList.toggle('hidden', totalCount === 0);
        }

        // 2. Actualizar lista en el Drawer lateral
        const cartList = document.getElementById('cart-items-list');
        if (cartList) {
            if (items.length === 0) {
                cartList.innerHTML = `
                    <div class="text-center py-12 text-gray-600">
                        <svg class="w-16 h-16 mx-auto mb-3 text-teal-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"></path>
                        </svg>
                        <p class="font-semibold text-teal-900">Tu carrito está vacío</p>
                        <p class="text-xs text-gray-600 mt-1">Agrega medicamentos o productos de cuidado personal.</p>
                    </div>
                `;
            } else {
                cartList.innerHTML = items.map(item => `
                    <div class="flex items-center justify-between bg-white p-3.5 rounded-xl border border-teal-100/80 shadow-sm">
                        <div class="flex items-center gap-3">
                            <img src="${item.image || 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?auto=format&fit=crop&w=400&q=80'}" 
                                 class="w-12 h-12 object-cover rounded-lg border border-gray-100">
                            <div>
                                <h4 class="font-bold text-gray-800 text-sm line-clamp-1">${item.name}</h4>
                                <span class="text-teal-700 font-extrabold text-xs">${this.formatCOP(item.price)}</span>
                            </div>
                        </div>

                        <div class="flex items-center gap-2">
                            <div class="flex items-center border border-gray-200 rounded-lg bg-gray-50">
                                <button onclick="Cart.updateQuantity('${item.id}', -1)" 
                                        class="px-2 py-0.5 text-gray-600 hover:text-orange-500 font-bold text-sm">-</button>
                                <span class="px-2 text-xs font-bold text-gray-800">${item.quantity}</span>
                                <button onclick="Cart.updateQuantity('${item.id}', 1)" 
                                        class="px-2 py-0.5 text-gray-600 hover:text-orange-500 font-bold text-sm">+</button>
                            </div>
                            <button onclick="Cart.removeItem('${item.id}')" 
                                    class="text-gray-400 hover:text-red-500 p-1">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                `).join('');
            }
        }

        // 3. Actualizar Subtotal y Envío
        const subtotalEl = document.getElementById('cart-subtotal');
        if (subtotalEl) subtotalEl.textContent = this.formatCOP(subtotal);

        const shippingEl = document.getElementById('cart-shipping');
        if (shippingEl) {
            shippingEl.textContent = subtotal > 50000 || subtotal === 0 ? 'GRATIS' : this.formatCOP(5000);
            shippingEl.className = subtotal > 50000 || subtotal === 0 
                ? 'font-bold text-teal-600' 
                : 'font-semibold text-gray-700';
        }
    },

    // --- Control de Interfaz ---

    openDrawer() {
        const drawer = document.getElementById('cart-drawer');
        const overlay = document.getElementById('cart-overlay');
        if (drawer && overlay) {
            drawer.classList.remove('translate-x-full');
            overlay.classList.remove('hidden');
        }
    },

    closeDrawer() {
        const drawer = document.getElementById('cart-drawer');
        const overlay = document.getElementById('cart-overlay');
        if (drawer && overlay) {
            drawer.classList.add('translate-x-full');
            overlay.classList.add('hidden');
        }
    },

    showToast(message) {
        const toast = document.getElementById('toast');
        const toastMsg = document.getElementById('toast-message');
        if (toast && toastMsg) {
            toastMsg.textContent = message;
            toast.classList.remove('translate-y-20', 'opacity-0');
            setTimeout(() => {
                toast.classList.add('translate-y-20', 'opacity-0');
            }, 2500);
        }
    },

    formatCOP(amount) {
        return new Intl.NumberFormat('es-CO', {
            style: 'currency',
            currency: 'COP',
            maximumFractionDigits: 0
        }).format(amount);
    }
};

// Event listener para inicializar el carrito al cargar la página
document.addEventListener('DOMContentLoaded', () => Cart.render());