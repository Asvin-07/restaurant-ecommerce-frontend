/**
 * main.js - Way To Food Frontend JavaScript
 * Handles: AJAX cart operations, toast notifications, UI interactions
 * No business logic - only UI interaction and API call coordination
 */
'use strict';

// --- CSRF Token ---
function getCsrfToken() {
  const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1].trim() : '';
}

// --- Toast Notification ----
function showToast(message, type = 'success') {
  // Remove existing toasts
  document.querySelectorAll('.wtf-toast').forEach(el => el.remove());

  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  const toast = document.createElement('div');
  toast.className = `wtf-toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || '•'}</span> ${message}`;
  document.body.appendChild(toast);

  // Auto-remove after animation completes
  setTimeout(() => toast.remove(), 1800);
}

// --- Loading Overlay ----
function showLoading() {
  if (document.getElementById('wtf-loading')) return;
  const overlay = document.createElement('div');
  overlay.id = 'wtf-loading';
  overlay.className = 'loading-overlay';
  overlay.innerHTML = `<div class="wtf-spinner"></div><p style="font-weight:700;color:#6c757d">Please wait...</p>`;
  document.body.appendChild(overlay);
}

function hideLoading() {
  const el = document.getElementById('wtf-loading');
  if (el) el.remove();
}

function parseMoneyText(text) {
  const num = Number(String(text || '').replace(/[^0-9.-]/g, ''));
  return Number.isFinite(num) ? num : null;
}

function setMoneyText(el, value) {
  if (!el || !Number.isFinite(value)) return;
  el.textContent = '₹' + value.toFixed(2);
}

function applySummaryDelta(delta) {
  if (!Number.isFinite(delta) || delta === 0) return;
  const subtotalEl = document.getElementById('summary-subtotal');
  const taxEl = document.getElementById('summary-tax');
  const totalEl = document.getElementById('summary-total');

  const subtotal = subtotalEl ? parseMoneyText(subtotalEl.textContent) : null;
  const tax = taxEl ? parseMoneyText(taxEl.textContent) : null;
  const total = totalEl ? parseMoneyText(totalEl.textContent) : null;

  if (subtotal !== null) {
    const nextSubtotal = Math.max(0, subtotal + delta);
    setMoneyText(subtotalEl, nextSubtotal);

    if (tax !== null && subtotal > 0) {
      // Keep tax/fee movement proportional to current effective tax rate.
      const taxRate = tax / subtotal;
      const nextTax = Math.max(0, nextSubtotal * taxRate);
      setMoneyText(taxEl, nextTax);
      if (total !== null) setMoneyText(totalEl, Math.max(0, nextSubtotal + nextTax));
      return;
    }
  }

  if (total !== null) setMoneyText(totalEl, Math.max(0, total + delta));
}

function applyCartBadgeDelta(delta) {
  if (!Number.isFinite(delta) || delta === 0) return;
  const badgeEl = document.querySelector('.cart-badge-count');
  const labelEl = document.querySelector('.cart-count-text');
  const current = badgeEl ? parseInt(badgeEl.textContent || '0', 10) :
    (labelEl ? (parseInt(labelEl.textContent || '0', 10) || 0) : 0);
  const next = Math.max(0, (Number.isFinite(current) ? current : 0) + delta);
  updateCartBadge(next);
}

// --- Cart Badge Update ---
function updateCartBadge(count) {
  document.querySelectorAll('.cart-badge-count').forEach(el => {
    el.textContent = count;
    el.style.display = count > 0 ? 'inline-flex' : 'none';
  });
  document.querySelectorAll('.cart-count-text').forEach(el => {
    el.textContent = count + (count === 1 ? ' Item' : ' Items');
  });
}

// --- Add to Cart ----
function addToCart(itemId, quantity = 1, instructions = '') {
  // Check login state before making any API call
  if (document.body.dataset.authenticated !== 'true') {
    showToast('Please log in to add items to cart.', 'error');
    setTimeout(() => { window.location.href = '/login/?next=/'; }, 1200);
    return Promise.resolve({ ok: false });
  }
  applyCartBadgeDelta(quantity);
  showToast('Added to cart!', 'success');
  return fetch('/cart/add/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify({ item_id: itemId, quantity, special_instructions: instructions })
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) {
        applyCartBadgeDelta(-quantity);
        showToast(data.error || 'Could not add item.', 'error');
      }
      return data;
    })
    .catch(() => {
      applyCartBadgeDelta(-quantity);
      showToast('Connection error. Please try again.', 'error');
    });
}

// --- Update Cart Item ---
function updateCartItem(cartItemId, quantity) {
  return fetch(`/cart/items/${cartItemId}/update/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify({ quantity })
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) showToast(data.error || 'Update failed.', 'error');
      return data;
    })
    .catch(() => showToast('Connection error.', 'error'));
}

// --- Remove Cart Item ---
function removeCartItem(cartItemId) {
  return fetch(`/cart/items/${cartItemId}/remove/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify({})
  })
    .then(r => r.json())
    .catch(() => showToast('Connection error.', 'error'));
}

// --- Clear Cart ----
function clearCart() {
  if (!confirm("Are you sure you want to clear your cart?")) return;

  fetch("/cart/clear/", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCsrfToken(),
      "Content-Type": "application/json"
    }
  })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        const cartList = document.getElementById("cart-items-list");
        if (cartList) cartList.innerHTML = "";

        document.getElementById("cart-main-section").style.display = "none";
        document.getElementById("cart-empty").style.display = "flex";

        const subtotal = document.getElementById("summary-subtotal");
        const tax = document.getElementById("summary-tax");
        const total = document.getElementById("summary-total");

        if (subtotal) subtotal.textContent = "₹0.00";
        if (tax) tax.textContent = "₹0.00";
        if (total) total.textContent = "₹0.00";

        updateCartBadge(0);
        const clearCartBtn = document.getElementById("btn-clear-cart");
        if (clearCartBtn) clearCartBtn.style.display = "none";
        showToast("Cart cleared", "info");
      } else {
        showToast(data.error || "Could not clear cart", "error");
      }
    })
    .catch(() => showToast("Connection error. Please try again.", "error"));
}

function decrementCartByItem(itemId) {
  applyCartBadgeDelta(-1);
  return fetch('/cart/decrement/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify({ item_id: itemId })
  })
    .then(r => r.json())
    .then(data => {
      if (!(data && data.ok)) {
        applyCartBadgeDelta(1);
        showToast((data && data.error) || 'Could not update cart.', 'error');
      }
      return data;
    })
    .catch(() => {
      applyCartBadgeDelta(1);
      showToast('Connection error. Please try again.', 'error');
    });
}

// --- Cart Page Re-render ---
function rerenderCart(cartData) {
  const items = cartData.items || [];
  const cartList = document.getElementById('cart-items-list');
  const emptyState = document.getElementById('cart-empty');
  const cartSection = document.getElementById('cart-main-section');

  if (!cartList) return;

  if (items.length === 0) {
    if (cartSection) cartSection.style.display = 'none';
    if (emptyState) emptyState.style.display = 'flex';
    updateCartBadge(0);
    const clearBtn = document.getElementById("btn-clear-cart");
    if (clearBtn) clearBtn.style.display = "none";
    return;
  }

  if (cartSection) cartSection.style.display = 'grid';
  if (emptyState) emptyState.style.display = 'none';
  const totalQty = items.reduce((sum, item) => sum + Number(item.quantity || 0), 0);
  updateCartBadge(totalQty);

  // Update summary
  const subtotal = cartData.subtotal || cartData.sub_total || 0;
  const tax = cartData.tax || 0;
  const total = cartData.total || 0;
  const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = '₹' + Number(val).toFixed(2); };
  setVal('summary-subtotal', subtotal);
  setVal('summary-tax', tax);
  setVal('summary-total', total);

  // Refresh each item row
  items.forEach(item => {
    const row = document.querySelector(`[data-cart-item-id="${item.id}"]`);
    if (row) {
      const qtyCtrlDisplay = row.querySelector('.qty-ctrl-display');
      const qtyInlineDisplay = row.querySelector('.qty-inline-display');
      const itemTotal = row.querySelector('.cart-item__price');
      if (qtyCtrlDisplay) qtyCtrlDisplay.textContent = item.quantity;
      if (qtyInlineDisplay) qtyInlineDisplay.textContent = item.quantity;
      if (itemTotal) itemTotal.textContent = '₹' + (item.unit_price * item.quantity).toFixed(2);
    }
  });

  // Remove rows that are no longer in the cart
  cartList.querySelectorAll('[data-cart-item-id]').forEach(row => {
    const id = row.dataset.cartItemId;
    if (!items.find(i => String(i.id) === id)) row.remove();
  });
}

function renderMenuGrid(items) {
  const menuGrid = document.querySelector('.menu-grid');
  const emptyState = document.querySelector('.empty-state');
  const filterEmpty = document.getElementById('menu-filter-empty');

  if (!menuGrid) return;

  if (!items || items.length === 0) {
    menuGrid.innerHTML = '';
    if (filterEmpty) filterEmpty.style.display = 'block';
    return;
  }

  if (filterEmpty) filterEmpty.style.display = 'none';

  menuGrid.innerHTML = items.map(item => `
    <div class="menu-card" data-category="${item.category || ''}">
      ${item.image
      ? `<img src="${item.image}" alt="${item.name}" class="menu-card__img" loading="lazy"
            onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">`
      : ''}
      <div class="menu-card__img-placeholder" ${item.image ? 'style="display:none"' : ''}>🍽️</div>

      <div class="menu-card__body"
          style="cursor:pointer;"
          data-item-id="${item.id}"
          data-item-name="${item.name || ''}"
          data-item-description="${item.description || ''}"
          data-item-price="${item.price || 0}"
          data-item-image="${item.image || ''}"
          data-item-is-veg="${item.is_veg ? 'true' : 'false'}"
          data-item-is-available="${item.is_available ? 'true' : 'false'}"
          data-item-category-name="${item.category_name || ''}">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:0.5rem;margin-bottom:0.3rem;">
          <h3 class="menu-card__title" style="margin:0;">${item.name}</h3>
          ${item.is_veg
      ? '<span class="veg-badge" title="Vegetarian"></span>'
      : '<span class="nveg-badge" title="Non-Vegetarian"></span>'}
        </div>

        ${item.category_name
      ? `<p style="font-size:0.75rem;color:#E67E22;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:0.4rem;">${item.category_name}</p>`
      : ''}

        <p class="menu-card__desc">
          ${item.description ? item.description.substring(0, 80) + (item.description.length > 80 ? '...' : '') : 'A delicious dish prepared fresh for you.'}
        </p>

        <div class="menu-card__footer">
          <span class="menu-card__price">₹${Math.round(item.price)}</span>
          ${item.is_available
      ? `<button class="btn-add" data-item-id="${item.id}">+ Add</button>`
      : '<span class="unavailable-label">Unavailable</span>'}
        </div>
      </div>
    </div>
  `).join('');
}

function getMenuItemFromCard(cardBody) {
  if (!cardBody) return null;
  const { dataset } = cardBody;

  return {
    id: dataset.itemId || '',
    name: dataset.itemName || '',
    description: dataset.itemDescription || '',
    price: Number(dataset.itemPrice || 0),
    image: dataset.itemImage || '',
    is_veg: dataset.itemIsVeg === 'true',
    is_available: dataset.itemIsAvailable === 'true',
    category_name: dataset.itemCategoryName || ''
  };
}

function openItemModal(item) {
  const overlay = document.getElementById('item-modal-overlay');
  const content = document.getElementById('item-modal-content');
  if (!overlay || !content) return;

  const vegBadge = item.is_veg
    ? '<span class="veg-badge" title="Vegetarian"></span>'
    : '<span class="nveg-badge" title="Non-Vegetarian"></span>';

  content.innerHTML = `
    <div class="item-modal__media">
      ${item.image
      ? `<img src="${item.image}" alt="${item.name}" class="item-modal__image" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';">`
      : ''}
      <div class="item-modal__placeholder" style="display:${item.image ? 'none' : 'flex'};">🍽️</div>
    </div>
    <div class="item-modal__body">
      <div class="item-modal__meta">
        ${vegBadge}
        ${item.category_name ? `<span class="item-modal__category">${item.category_name}</span>` : ''}
      </div>
      <h2 class="item-modal__title">${item.name}</h2>
      <p class="item-modal__description">${item.description || 'A delicious dish prepared fresh with the finest ingredients.'}</p>
      <div class="item-modal__price">₹${Math.round(item.price)}</div>
      ${item.is_available
      ? `<button onclick="addToCart('${item.id}', 1); closeItemModal();" class="btn-primary-wtf item-modal__action">🛒 Add to Cart</button>`
      : `<div class="item-modal__unavailable">⚠ Currently unavailable</div>`}
    </div>
  `;
  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeItemModal() {
  const overlay = document.getElementById('item-modal-overlay');
  if (overlay) overlay.classList.remove('open');
  document.body.style.overflow = '';
}

// ─── DOM Ready ───
document.addEventListener('DOMContentLoaded', () => {

  const clearBtn = document.getElementById("btn-clear-cart");
  if (clearBtn) {
    clearBtn.addEventListener("click", clearCart);
  }

  // Menu page: in-place category filter + delegated Add-to-Cart handling
  const menuGrid = document.querySelector('.menu-grid');
  const categoryPills = document.querySelector('.category-pills');
  const filterEmpty = document.getElementById('menu-filter-empty');

  if (categoryPills && menuGrid) {
    categoryPills.addEventListener('click', function (e) {
      const pill = e.target.closest('.cat-pill');
      if (!pill) return;

      const href = pill.getAttribute('href') || '';

      // Intercept all category pills
      e.preventDefault();

      // Update which pill looks active
      categoryPills.querySelectorAll('.cat-pill').forEach(el => el.classList.remove('active'));
      pill.classList.add('active');

      // Get category ID from the URL in the href
      const hrefParams = new URLSearchParams(href.split('?')[1] || '');
      const categoryId = hrefParams.get('category') || '';

      // Update the browser address bar (no reload)
      const newUrl = categoryId ? `/?category=${categoryId}` : '/';
      window.history.pushState({}, '', newUrl);

      // Fade the grid to show loading
      menuGrid.style.opacity = '0.5';
      menuGrid.style.pointerEvents = 'none';

      // Build the API URL and fetch
      const apiUrl = categoryId
        ? `/api/menu-items/?category=${categoryId}`
        : `/api/menu-items/`;

      fetch(apiUrl)
        .then(r => r.json())
        .then(data => {
          menuGrid.style.opacity = '1';
          menuGrid.style.pointerEvents = '';
          if (!data.ok) {
            showToast('Could not load items.', 'error');
            return;
          }
          renderMenuGrid(data.items);
        })
        .catch(() => {
          menuGrid.style.opacity = '1';
          menuGrid.style.pointerEvents = '';
          showToast('Connection error.', 'error');
        });
    });
  }
  
  // Close modal when clicking the dark backdrop
  const modalOverlay = document.getElementById('item-modal-overlay');
  if (modalOverlay) {
    modalOverlay.addEventListener('click', function (e) {
      if (e.target === this) closeItemModal();
    });
  }

  if (menuGrid) {
    menuGrid.addEventListener('click', function (e) {
      const addBtn = e.target.closest('.btn-add[data-item-id]');
      if (addBtn) {
        const itemId = addBtn.dataset.itemId;
        addBtn.outerHTML = `
          <div class="inline-qty-ctrl" data-item-id="${itemId}">
            <button class="qty-btn minus">−</button>
            <span class="qty-display">1</span>
            <button class="qty-btn plus">+</button>
          </div>`;

        addToCart(itemId, 1).then(data => {
          if (!data || !data.ok) {
            const inlineCtrl = document.querySelector(`.inline-qty-ctrl[data-item-id="${itemId}"]`);
            if (inlineCtrl) {
              inlineCtrl.outerHTML = `<button class="btn-add" data-item-id="${itemId}">+ Add</button>`;
            }
          }
        });
        return;
      }

      const ctrlBtn = e.target.closest('.inline-qty-ctrl .qty-btn');
      if (ctrlBtn) {
        const ctrl = ctrlBtn.closest('.inline-qty-ctrl');
        const display = ctrl ? ctrl.querySelector('.qty-display') : null;
        if (!ctrl || !display) return;

        const itemId = ctrl.dataset.itemId;
        const previousQty = parseInt(display.textContent || '1', 10);
        let qty = previousQty;

        if (ctrlBtn.classList.contains('plus')) {
          qty += 1;
          display.textContent = qty;
          addToCart(itemId, 1);
          return;
        }

        qty -= 1;
        if (qty <= 0) {
          const card = ctrl.closest('.menu-card');
          // Optimistic: reflect removal instantly on menu card.
          ctrl.outerHTML = `<button class="btn-add" data-item-id="${itemId}">+ Add</button>`;
          decrementCartByItem(itemId).then(data => {
            if (!(data && data.ok)) {
              const btn = (card || menuGrid).querySelector(`.btn-add[data-item-id="${itemId}"]`);
              if (btn) {
                btn.outerHTML = `
                  <div class="inline-qty-ctrl" data-item-id="${itemId}">
                    <button class="qty-btn minus">−</button>
                    <span class="qty-display">1</span>
                    <button class="qty-btn plus">+</button>
                  </div>`;
              }
            }
          });
        } else {
          // Optimistic: reflect decrement instantly on menu card.
          display.textContent = qty;
          decrementCartByItem(itemId).then(data => {
            if (!(data && data.ok)) {
              display.textContent = previousQty;
            }
          });
        }
        return;
      }

      const cardBody = e.target.closest('.menu-card__body');
      if (!cardBody) return;

      const item = getMenuItemFromCard(cardBody);
      if (item) openItemModal(item);
    });
  }

  function optimisticRemoveFromCart(row) {
    if (!row) return { removedQty: 0, removedAmount: 0 };
    const removedQty = Number(row.querySelector('.qty-ctrl-display')?.textContent || 1);
    const unitPrice = Number(row.dataset.unitPrice || 0);
    const removedAmount = removedQty * unitPrice;

    row.remove();
    if (removedAmount > 0) applySummaryDelta(-removedAmount);
    if (removedQty > 0) applyCartBadgeDelta(-removedQty);

    const cartList = document.getElementById('cart-items-list');
    const cartSection = document.getElementById('cart-main-section');
    const emptyState = document.getElementById('cart-empty');
    if (cartList && cartSection && emptyState && !cartList.querySelector('[data-cart-item-id]')) {
      cartSection.style.display = 'none';
      emptyState.style.display = 'flex';
      const clearBtn = document.getElementById("btn-clear-cart");
      if (clearBtn) clearBtn.style.display = "none";
    }

    return { removedQty, removedAmount };
  }

  // Quantity controls on cart page
  document.querySelectorAll('.qty-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const row = this.closest('[data-cart-item-id]');
      if (!row) return;
      const cartItemId = row.dataset.cartItemId;
      const qtyCtrlDisplay = row.querySelector('.qty-ctrl-display');
      const qtyInlineDisplay = row.querySelector('.qty-inline-display');
      const itemTotal = row.querySelector('.cart-item__price');
      if (!qtyCtrlDisplay) return;

      const previousQty = parseInt(qtyCtrlDisplay.textContent, 10);
      let qty = previousQty;

      if (this.classList.contains('minus')) {
        if (qty <= 1) {
          // Save exactly where the row was before removing it
          const parentNode = row.parentNode;
          const nextSibling = row.nextSibling;

          const { removedQty, removedAmount } = optimisticRemoveFromCart(row);
          showToast('Item removed.', 'info');
          removeCartItem(cartItemId).then(data => {
            if (data && data.ok) {
              rerenderCart(data.cart);
            } else {
              showToast((data && data.error) || 'Could not remove item.', 'error');
              if (removedAmount > 0) applySummaryDelta(removedAmount);
              if (removedQty > 0) applyCartBadgeDelta(removedQty);

              // Graceful restore instead of page reload
              if (nextSibling) parentNode.insertBefore(row, nextSibling);
              else parentNode.appendChild(row);

              document.getElementById('cart-main-section').style.display = 'grid';
              document.getElementById('cart-empty').style.display = 'none';
            }
          });
          return;
        }
        qty -= 1;
      } else {
        qty += 1;
      }

      qtyCtrlDisplay.textContent = qty;
      if (qtyInlineDisplay) qtyInlineDisplay.textContent = qty;

      // Optimistic row total update
      const unitPrice = Number(row.dataset.unitPrice || 0);
      if (itemTotal && unitPrice > 0) {
        itemTotal.textContent = '₹' + (unitPrice * qty).toFixed(2);
      }
      if (unitPrice > 0) {
        applySummaryDelta(unitPrice * (qty - previousQty));
      }
      applyCartBadgeDelta(qty - previousQty);

      updateCartItem(cartItemId, qty).then(data => {
        if (data && data.ok) rerenderCart(data.cart);
        else {
          qtyCtrlDisplay.textContent = previousQty;
          if (qtyInlineDisplay) qtyInlineDisplay.textContent = previousQty;
          if (itemTotal && unitPrice > 0) {
            itemTotal.textContent = '₹' + (unitPrice * previousQty).toFixed(2);
          }
          if (unitPrice > 0) {
            applySummaryDelta(unitPrice * (previousQty - qty));
          }
          applyCartBadgeDelta(previousQty - qty);
        }
      });
    });
  });

  // Remove-item buttons on cart page
  document.querySelectorAll('.btn-remove[data-cart-item-id]').forEach(btn => {
    btn.addEventListener('click', function () {
      const cartItemId = this.dataset.cartItemId;
      const row = document.querySelector(`[data-cart-item-id="${cartItemId}"]`);

      // Save exactly where the row was before removing it
      const parentNode = row.parentNode;
      const nextSibling = row.nextSibling;

      const { removedQty, removedAmount } = optimisticRemoveFromCart(row);
      showToast('Item removed from cart.', 'info');
      removeCartItem(cartItemId).then(data => {
        if (data && data.ok) {
          rerenderCart(data.cart);
        } else {
          showToast((data && data.error) || 'Could not remove item.', 'error');
          if (removedAmount > 0) applySummaryDelta(removedAmount);
          if (removedQty > 0) applyCartBadgeDelta(removedQty);

          // Graceful restore instead of page reload
          if (nextSibling) parentNode.insertBefore(row, nextSibling);
          else parentNode.appendChild(row);

          document.getElementById('cart-main-section').style.display = 'grid';
          document.getElementById('cart-empty').style.display = 'none';
        }
      });
    });
  });

  // Item detail add-to-cart form
  const detailForm = document.getElementById('item-detail-form');
  if (detailForm) {
    detailForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const itemId = this.dataset.itemId;
      const qty = parseInt(document.getElementById('detail-qty')?.value || '1');
      const instructions = document.getElementById('detail-instructions')?.value || '';
      const btn = this.querySelector('button[type="submit"]');
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Adding...';
      addToCart(itemId, qty, instructions).finally(() => {
        btn.disabled = false;
        btn.textContent = originalText;
      });
    });
  }

  // Search form - remove empty params
  const searchForm = document.getElementById('menu-search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', function (e) {
      const input = this.querySelector('input[name="search"]');
      if (input && !input.value.trim()) {
        e.preventDefault();
        window.location.href = '/';
      }
    });
  }

  // Checkout form - show loading on submit & validate address
  const checkoutForm = document.getElementById('checkout-form');
  if (checkoutForm) {
    checkoutForm.addEventListener('submit', function (e) {

      // 1. Validate Address Length
      const addressInput = document.querySelector('textarea[name="delivery_address"]');
      if (addressInput && addressInput.value.trim().length < 12) {
        e.preventDefault(); // Stop the form from submitting
        showToast('Please enter your complete address (House No, Street, etc.)', 'error');
        addressInput.focus(); // Put the blinking cursor back in the box
        return;
      }

      // 2. Show Loading State
      const btn = this.querySelector('button[type="submit"]');
      if (btn) {
        if (btn.disabled) return;
        btn.disabled = true;
        btn.textContent = 'Placing Order...';
        showLoading();
      }
    });
  }

  //Global form double-submission prevention (Auth, Profile, etc.)
  document.querySelectorAll('form[method="POST"]').forEach(form => {
    // Skip forms that already have custom submit listeners
    if (form.id === 'checkout-form' || form.id === 'item-detail-form') return;

    // Skip forms marked as no-loading (e.g. logout)
    if (form.hasAttribute('data-no-loading')) return;

    form.addEventListener('submit', function () {
      const btn = this.querySelector('button[type="submit"]');
      if (btn) {
        if (btn.disabled) return;
        btn.disabled = true;

        const originalText = btn.textContent.trim();
        btn.textContent = originalText + '...';
        showLoading();
      }
    });
  });

  // Auto-dismiss Django messages after 5s
  document.querySelectorAll('.wtf-django-alert').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.5s';
      el.style.opacity = '0';
      setTimeout(() => {
        const parent = el.parentElement;
        el.remove();
        if (parent && parent.querySelectorAll('.wtf-django-alert').length === 0) { parent.remove(); }
      }, 500);
    }, 5000);
  });

  // --- Location startup - runs on every page ---
  let savedLocation = sessionStorage.getItem('wtf_user_location');
  const locationSkipped = sessionStorage.getItem('wtf_location_skipped');

  const navbarLocation = document.getElementById('navbar-location');
  const navbarLocationText = document.getElementById('navbar-location-text');

  // 1. Sync Backend location to Frontend memory (Ignore dummy text)
  if (!savedLocation && navbarLocationText) {
    const dbLocation = navbarLocationText.textContent.trim();
    const ignoreList = ['', 'Location not set', 'Set Location', 'Locating...'];

    if (!ignoreList.includes(dbLocation)) {
      savedLocation = dbLocation;
      sessionStorage.setItem('wtf_user_location', savedLocation);
    }
  }

  if (savedLocation) {
    if (navbarLocation && navbarLocationText) {
      navbarLocationText.textContent = savedLocation;
      navbarLocation.style.display = 'flex';
    }

    const reminder = document.getElementById('location-reminder');
    if (reminder) {
      reminder.style.display = 'none';
    }

    const addressInput = document.querySelector('textarea[name="delivery_address"]');
    if (addressInput && addressInput.value.trim() === '') {
      addressInput.value = savedLocation;
    }

    const warningBox = document.getElementById('checkout-location-warning');
    if (warningBox) {
      warningBox.style.display = 'none';
    }

  } else {
    if (navbarLocationText && navbarLocationText.textContent.trim() === 'Locating...') {
      if (navbarLocation) navbarLocation.style.display = 'none';
    }

    if (locationSkipped) {
      const reminder = document.getElementById('location-reminder');
      if (reminder) reminder.style.display = 'flex';
    } else {
      if (window.location.pathname === '/') {
        setTimeout(showLocationPopup, 800);
      }
    }
  }
  initBannerSlider();
});

// --- Location Feature ----

function showLocationPopup() {
  const overlay = document.getElementById('location-overlay');
  if (!overlay) return;
  const btn = document.getElementById('btn-detect-location');
  if (btn) {
    btn.innerHTML = '<span>📡</span> Use My Current Location';
    btn.disabled = false;
  }
  const status = document.getElementById('location-status');
  if (status) status.textContent = '';
  overlay.style.display = 'flex';
}

function hideLocationPopup() {
  const overlay = document.getElementById('location-overlay');
  if (overlay) overlay.style.display = 'none';
}

function setLocationDisplay(locationText) {
  const navbarLocation = document.getElementById('navbar-location');
  const navbarLocationText = document.getElementById('navbar-location-text');
  if (navbarLocation && navbarLocationText) {
    navbarLocationText.textContent = locationText;
    navbarLocation.style.display = 'flex';
  }
  // Hide reminder banner 
  const reminder = document.getElementById('location-reminder');
  if (reminder) reminder.style.display = 'none';

  // Auto-fill the delivery address
  const addressInput = document.querySelector('textarea[name="delivery_address"]');
  if (addressInput && addressInput.value.trim() === '') {
    addressInput.value = locationText;
  }

  // Hide the  warning box
  const warningBox = document.getElementById('checkout-location-warning');
  if (warningBox) {
    warningBox.style.display = 'none';
  }

  sessionStorage.setItem('wtf_user_location', locationText);
}

function detectLocation() {
  const btn = document.getElementById('btn-detect-location');
  const status = document.getElementById('location-status');

  if (!navigator.geolocation) {
    status.textContent = '⚠ Your browser does not support location detection.';
    status.style.color = '#C0392B';
    return;
  }

  btn.innerHTML = '⏳ Detecting your location...';
  btn.disabled = true;
  status.textContent = '';

  navigator.geolocation.getCurrentPosition(
    function (position) {
      const lat = position.coords.latitude;
      const lng = position.coords.longitude;

      fetch('https://nominatim.openstreetmap.org/reverse?lat=' + lat + '&lon=' + lng + '&format=json')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          const address = data.address || {};
          const locationText = address.suburb
            || address.neighbourhood
            || address.city_district
            || address.city
            || address.town
            || address.village
            || 'Near You';

          setLocationDisplay(locationText);
          hideLocationPopup();
          showToast('Location set to ' + locationText, 'success');
        })
        .catch(function () {
          setLocationDisplay('Near You');
          hideLocationPopup();
          showToast('Location detected!', 'success');
        });
    },
    function (error) {
      btn.innerHTML = '<span>📡</span> Use My Current Location';
      btn.disabled = false;

      if (error.code === error.PERMISSION_DENIED) {
        status.textContent = '⚠ Permission denied. Please enter your location manually.';
      } else if (error.code === error.POSITION_UNAVAILABLE) {
        status.textContent = '⚠ Location unavailable. Please enter manually.';
      } else {
        status.textContent = '⚠ Request timed out. Please enter manually.';
      }
      status.style.color = '#C0392B';
    },
    { timeout: 10000, maximumAge: 300000 }
  );
}

function saveManualLocation() {
  const input = document.getElementById('manual-location-input');
  const status = document.getElementById('location-status');

  if (!input || !input.value.trim()) {
    status.textContent = '⚠ Please enter your area or city name.';
    status.style.color = '#C0392B';
    return;
  }

  setLocationDisplay(input.value.trim());
  hideLocationPopup();
  showToast('Location set to ' + input.value.trim(), 'success');
}

function skipLocation() {
  sessionStorage.setItem('wtf_location_skipped', 'true');
  hideLocationPopup();
  // Reminder banner 
  const reminder = document.getElementById('location-reminder');
  if (reminder) reminder.style.display = 'flex';
}

// --- Category Strip Scroll Fades ---
const strip = document.querySelector('.category-pills');
const inner = document.querySelector('.category-strip-inner');

function updateFades() {
  if (!strip || !inner) return;
  const scrollLeft = strip.scrollLeft;
  const maxScroll = strip.scrollWidth - strip.clientWidth;

  // Left fade - only show if scrolled right
  inner.classList.toggle('show-fade-left', scrollLeft > 10);

  // Right fade - only show if more content to the right
  inner.classList.toggle('show-fade-right', scrollLeft < maxScroll - 10);
}

if (strip) {
  strip.addEventListener('scroll', updateFades);
  // Run once on load
  updateFades();
}

// --- Draggable Scroll for Category Pills ---
const pillsContainer = document.querySelector('.category-pills');
if (pillsContainer) {
  let isDown = false;
  let startX;
  let scrollLeft;
  let hasDragged = false;  // fix 3: distinguish click from drag

  // Fix 1: prevent ghost image when dragging text/elements
  pillsContainer.addEventListener('dragstart', (e) => e.preventDefault());

  pillsContainer.addEventListener('mousedown', (e) => {
    isDown = true;
    hasDragged = false;
    startX = e.pageX - pillsContainer.offsetLeft;
    scrollLeft = pillsContainer.scrollLeft;
  });

  pillsContainer.addEventListener('mouseleave', () => {
    isDown = false;
    pillsContainer.style.cursor = 'grab';
  });

  pillsContainer.addEventListener('mouseup', () => {
    isDown = false;
    pillsContainer.style.cursor = 'grab';
  });

  pillsContainer.addEventListener('mousemove', (e) => {
    if (!isDown) return;
    e.preventDefault(); // Fix 2: prevent text selection while dragging
    const x = e.pageX - pillsContainer.offsetLeft;
    const walk = (x - startX) * 1.5;

    // Only activate drag if moved more than 5px - fix 3
    if (Math.abs(walk) > 5) {
      hasDragged = true;
      pillsContainer.style.cursor = 'grabbing';
      pillsContainer.scrollLeft = scrollLeft - walk;
      updateFades();
    }
  });

  // Fix 3: block pill click if it was actually a drag
  pillsContainer.addEventListener('click', (e) => {
    if (hasDragged) {
      e.preventDefault();
      e.stopPropagation();
      hasDragged = false;
    }
  }, true);

  pillsContainer.style.cursor = 'grab';
}

// Banner Slideshow
function initBannerSlider() {
    const slides = document.querySelectorAll('.banner-slide');
    const dots = document.querySelectorAll('.banner-dot');
    if (slides.length <= 1) return;

    let current = 0;

    function goTo(index) {
        slides[current].style.display = 'none';
        dots[current].style.background = 'rgba(255,255,255,0.5)';
        current = index;
        slides[current].style.display = 'block';
        dots[current].style.background = 'rgba(255,255,255,1)';
    }

    dots.forEach((dot, i) => dot.addEventListener('click', () => goTo(i)));
    setInterval(() => goTo((current + 1) % slides.length), 10000);
}