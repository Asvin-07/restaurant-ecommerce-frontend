/**
 * main.js — Way To Food Frontend JavaScript
 * Handles: AJAX cart operations, toast notifications, UI interactions
 * No business logic — only UI interaction and API call coordination
 */

'use strict';

// ─── CSRF Token ────────────────────────────────────────────
function getCsrfToken() {
  const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1].trim() : '';
}

// ─── Toast Notification ────────────────────────────────────
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

// ─── Loading Overlay ───────────────────────────────────────
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

// ─── Cart Badge Update ─────────────────────────────────────
function updateCartBadge(count) {
  document.querySelectorAll('.cart-badge-count').forEach(el => {
    el.textContent = count;
    el.style.display = count > 0 ? 'inline-flex' : 'none';
  });
  document.querySelectorAll('.cart-count-text').forEach(el => {
    el.textContent = count + (count === 1 ? ' Item' : ' Items');
  });
}

// ─── Add to Cart ───────────────────────────────────────────
function addToCart(itemId, quantity = 1, instructions = '') {
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

// ─── Update Cart Item ──────────────────────────────────────
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

// ─── Remove Cart Item ──────
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

// ─── Clear Cart ──────
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

// ─── Cart Page Re-render ───────────────────────────────────
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

  function applyCategoryFilter(filterCat) {
    if (!menuGrid) return;
    const cards = menuGrid.querySelectorAll('.menu-card[data-category]');
    let visibleCount = 0;

    cards.forEach(card => {
      const cardCat = card.dataset.category || '';
      const show = (filterCat === 'all' || cardCat === filterCat);
      card.style.display = show ? '' : 'none';
      if (show) visibleCount += 1;
    });

    if (filterEmpty) filterEmpty.style.display = visibleCount === 0 ? 'block' : 'none';
  }

  if (categoryPills && menuGrid) {
    categoryPills.addEventListener('click', function (e) {
      const pill = e.target.closest('.cat-pill[data-filter-cat]');
      if (!pill) return;
      e.preventDefault();

      const filterCat = pill.dataset.filterCat || 'all';
      categoryPills.querySelectorAll('.cat-pill').forEach(el => el.classList.remove('active'));
      pill.classList.add('active');
      applyCategoryFilter(filterCat);
    });

    const activePill = categoryPills.querySelector('.cat-pill.active[data-filter-cat]');
    applyCategoryFilter(activePill ? activePill.dataset.filterCat : 'all');
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
      if (!ctrlBtn) return;

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

      // Optimistic row total update for snappier UI
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

  // Search form — remove empty params
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

  // Checkout form — show loading on submit
  const checkoutForm = document.getElementById('checkout-form');
  if (checkoutForm) {
    checkoutForm.addEventListener('submit', function () {
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
      setTimeout(() => el.remove(), 500);
    }, 5000);
  });
  // ── Location startup — runs on every page ──────────────
  const savedLocation = sessionStorage.getItem('wtf_user_location');
  const locationSkipped = sessionStorage.getItem('wtf_location_skipped');

  if (savedLocation) {
    // Restore display only — don't call setLocationDisplay
    // because that would unnecessarily rewrite sessionStorage
    const navbarLocation = document.getElementById('navbar-location');
    const navbarLocationText = document.getElementById('navbar-location-text');
    if (navbarLocation && navbarLocationText) {
      navbarLocationText.textContent = savedLocation;
      navbarLocation.style.display = 'flex';
    }
    const reminder = document.getElementById('location-reminder');
    if (reminder) reminder.style.display = 'none';
  } else if (locationSkipped) {
    const reminder = document.getElementById('location-reminder');
    if (reminder) reminder.style.display = 'flex';
  } else {
    // Only auto-popup on home/menu page
    if (window.location.pathname === '/') {
      setTimeout(showLocationPopup, 800);
    }
  }
});

// ─── Location Feature ──────────────────────────────────────

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
  // Hide reminder banner since location is now set
  const reminder = document.getElementById('location-reminder');
  if (reminder) reminder.style.display = 'none';

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
  // Show reminder banner so user knows they can set it anytime
  const reminder = document.getElementById('location-reminder');
  if (reminder) reminder.style.display = 'flex';
}