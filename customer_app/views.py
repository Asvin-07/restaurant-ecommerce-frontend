"""
views.py — Customer-facing views for Way To Food (WTF)
- Menu and item browsing works without login (guests welcome)
- Cart works for guests using session-based token
- Checkout, orders, profile require login
- Guest cart merges into user cart after login at checkout
"""

from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json
import uuid

from . import api_service as api

# ─── Auth Helpers ─────────────────────────────────────────────────────────────

def _get_token(request):
    """Get auth token for logged-in user."""
    return request.session.get("auth_token")

def _get_user(request):
    """Get logged-in user info from session."""
    return request.session.get("user_info", {})

def _get_cart_token(request):
    """
    Get the token to use for cart operations.
    - If logged in: use auth token
    - If guest: use/create a guest session token
    """
    token = _get_token(request)
    if token:
        return token

    # Guest — use or create a session-based cart token
    guest_token = request.session.get("guest_cart_token")
    if not guest_token:
        guest_token = "guest-" + str(uuid.uuid4())[:8]
        request.session["guest_cart_token"] = guest_token
        request.session.modified = True
    return guest_token

def _login_required(view_func):
    """Redirect to login if not authenticated."""
    def wrapper(request, *args, **kwargs):
        if not _get_token(request):
            messages.warning(request, "Please log in to continue.")
            return redirect(f"{reverse('login')}?next={request.path}")
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper

def _set_session(request, token, user):
    request.session["auth_token"] = token
    request.session["user_info"] = user
    request.session.modified = True

def _clear_session(request):
    request.session.pop("auth_token", None)
    request.session.pop("user_info", None)
    request.session.modified = True

def _get_cart_count(request):
    """Get cart item count using correct token (guest or logged-in)."""
    token = _get_cart_token(request)
    result = api.get_cart(token=token)
    if result and result.get("ok"):
        return sum(int(item.get("quantity", 0)) for item in result.get("data", {}).get("items", []))
    return 0

def _merge_guest_cart(request):
    """
    After login, merge guest cart into user cart.
    Called at checkout when user just logged in.
    """
    guest_token = request.session.get("guest_cart_token")
    user_token  = _get_token(request)

    if not guest_token or not user_token or guest_token == user_token:
        return

    guest_cart = api.get_cart(token=guest_token)
    if guest_cart.get("ok"):
        for item in guest_cart.get("data", {}).get("items", []):
            api.add_to_cart(
                token=user_token,
                item_id=item["item_id"],
                quantity=item["quantity"],
                special_instructions=item.get("special_instructions", "")
            )

    # Clear guest token from session
    request.session.pop("guest_cart_token", None)
    request.session.modified = True

# ─── Authentication Views ─────────────────────────────────────────────────────

def login_view(request):
    if _get_token(request):
        return redirect("menu")

    if request.method == "POST":
        phone = request.POST.get("phone", "").strip()
        otp   = request.POST.get("otp", "").strip()

        if not phone:
            messages.error(request, "Please enter your mobile number.")
            return render(request, "login.html")

        # Step 1 — phone submitted, no OTP yet → send OTP
        if not otp:
            result = api.send_otp(phone=phone)
            if result["ok"]:
                messages.success(request, f"OTP sent to {phone}")
                next_url = request.POST.get("next") or request.GET.get("next", "")
                return render(request, "login.html", {"phone": phone, "otp_sent": True, "next_url": next_url})
            else:
                messages.error(request, result.get("error", "Could not send OTP."))
                return render(request, "login.html")

        # Step 2 — OTP submitted → verify and login
        result = api.verify_otp(phone=phone, otp=otp)
        if result["ok"]:
            data = result["data"]
            _set_session(request, token=data.get("token"), user=data.get("user", {}))
            next_url = request.POST.get("next") or request.GET.get("next", "menu")
            return redirect(next_url)
        else:
            messages.error(request, result.get("error", "Invalid OTP. Please try again."))
            next_url = request.POST.get("next") or request.GET.get("next", "")
            return render(request, "login.html", {"phone": phone, "otp_sent": True, "next_url": next_url})

    return render(request, "login.html")

def register_view(request):
    if _get_token(request):
        return redirect("menu")
    if request.method == "POST":
        name     = request.POST.get("name", "").strip()
        phone    = request.POST.get("phone", "").strip()
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        confirm  = request.POST.get("confirm_password", "").strip()
        errors   = []
        if not name:                           errors.append("Full name is required.")
        if not phone or len(phone) < 10:       errors.append("A valid 10-digit phone number is required.")
        if not email or "@" not in email:      errors.append("A valid email address is required.")
        if len(password) < 6:                  errors.append("Password must be at least 6 characters.")
        if password != confirm:                errors.append("Passwords do not match.")
        if errors:
            for err in errors:
                messages.error(request, err)
            return render(request, "register.html", {"form_data": {"name": name, "phone": phone, "email": email}})
        result = api.register(name=name, phone=phone, email=email, password=password)
        if result["ok"]:
            data = result["data"]
            _set_session(request, token=data.get("token"), user=data.get("user", {}))
            messages.success(request, f"Welcome, {name}!")
            return redirect("menu")
        else:
            messages.error(request, result.get("error", "Registration failed."))
            return render(request, "register.html", {"form_data": {"name": name, "phone": phone, "email": email}})
    return render(request, "register.html")

def logout_view(request):
    _clear_session(request)
    messages.success(request, "You have been logged out.")
    return redirect("menu")

# ─── Menu Views ───────────────────────────────────────────────────────────────

def menu_view(request):
    """Public — no login required."""
    token        = _get_token(request)   # None for guests — that's fine
    search_query = request.GET.get("search", "")

    cat_result   = api.get_categories(token=token)
    categories   = cat_result.get("data", []) if cat_result["ok"] else []

    items_result = api.get_menu_items(
        token=token,
        search=search_query or None
    )
    menu_items = items_result.get("data", []) if items_result["ok"] else []

    if not items_result["ok"]:
        messages.error(request, items_result.get("error", "Could not load menu."))

    return render(request, "menu.html", {
        "categories":        categories,
        "menu_items":        menu_items,
        "selected_category": "",
        "search_query":      search_query,
        "cart_count":        _get_cart_count(request),
        "user":              _get_user(request),
    })

def item_detail_view(request, item_id):
    """Public — no login required."""
    token  = _get_token(request)
    result = api.get_menu_item_detail(item_id=item_id, token=token)
    if not result["ok"]:
        messages.error(request, "Item not found.")
        return redirect("menu")
    return render(request, "item_detail.html", {
        "item":       result["data"],
        "cart_count": _get_cart_count(request),
        "user":       _get_user(request),
    })

# ─── Cart AJAX Views (work for guests too) ────────────────────────────────────

@require_http_methods(["POST"])
def add_to_cart_view(request):
    """Add item to cart — works for both guests and logged-in users."""
    token = _get_cart_token(request)   # always returns a valid token

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    result = api.add_to_cart(
        token=token,
        item_id=body.get("item_id"),
        quantity=int(body.get("quantity", 1)),
        special_instructions=body.get("special_instructions", "")
    )

    if result["ok"]:
        cart_result = api.get_cart(token=token)
        count = (
            sum(int(item.get("quantity", 0)) for item in cart_result.get("data", {}).get("items", []))
            if cart_result["ok"] else 0
        )
        return JsonResponse({"ok": True, "cart_count": count, "message": "Added to cart!"})

    return JsonResponse({"ok": False, "error": result.get("error", "Could not add item.")}, status=400)

@require_http_methods(["POST"])
def update_cart_item_view(request, cart_item_id):
    """Update cart item quantity — works for guests too."""
    token = _get_cart_token(request)

    try:
        body     = json.loads(request.body)
        quantity = int(body.get("quantity", 1))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    result = api.update_cart_item(token=token, cart_item_id=cart_item_id, quantity=quantity)
    if result["ok"]:
        cart_result = api.get_cart(token=token)
        return JsonResponse({"ok": True, "cart": cart_result.get("data", {})})
    return JsonResponse({"ok": False, "error": result.get("error", "Update failed.")}, status=400)

@require_http_methods(["POST"])
def remove_cart_item_view(request, cart_item_id):
    """Remove cart item — works for guests too."""
    token  = _get_cart_token(request)
    result = api.remove_cart_item(token=token, cart_item_id=cart_item_id)
    if result["ok"]:
        cart_result = api.get_cart(token=token)
        return JsonResponse({"ok": True, "cart": cart_result.get("data", {})})
    return JsonResponse({"ok": False, "error": result.get("error", "Could not remove item.")}, status=400)

@require_http_methods(["POST"])
def clear_cart_view(request):
    """Clear the entire cart — works for guests too."""
    token = _get_cart_token(request)
    result = api.clear_cart(token=token)

    if result["ok"]:
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "error": result.get("error", "Could not clear cart.")}, status=400)

@require_http_methods(["POST"])
def decrement_cart_item_by_item_id_view(request):
    """Decrement cart quantity by menu item_id — used from menu cards."""
    token = _get_cart_token(request)

    try:
        body = json.loads(request.body)
        item_id = str(body.get("item_id", "")).strip()
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    if not item_id:
        return JsonResponse({"ok": False, "error": "Item id is required."}, status=400)

    cart_result = api.get_cart(token=token)
    if not cart_result.get("ok"):
        return JsonResponse({"ok": False, "error": "Could not load cart."}, status=400)

    cart_items = cart_result.get("data", {}).get("items", [])
    target = next((x for x in cart_items if str(x.get("item_id")) == item_id), None)

    if not target:
        count = sum(int(item.get("quantity", 0)) for item in cart_items)
        return JsonResponse({"ok": True, "cart_count": count})

    current_qty = int(target.get("quantity", 0))
    cart_item_id = target.get("id")
    if not cart_item_id:
        return JsonResponse({"ok": False, "error": "Cart item not found."}, status=400)

    if current_qty <= 1:
        result = api.remove_cart_item(token=token, cart_item_id=cart_item_id)
    else:
        result = api.update_cart_item(token=token, cart_item_id=cart_item_id, quantity=current_qty - 1)

    if not result.get("ok"):
        return JsonResponse({"ok": False, "error": result.get("error", "Could not update cart.")}, status=400)

    updated = api.get_cart(token=token)
    count = (
        sum(int(item.get("quantity", 0)) for item in updated.get("data", {}).get("items", []))
        if updated.get("ok") else 0
    )
    return JsonResponse({"ok": True, "cart_count": count})

# ─── Cart Page ────────────────────────────────────────────────────────────────

def cart_view(request):
    """Cart page — works for guests too."""
    token  = _get_cart_token(request)
    result = api.get_cart(token=token)

    cart_data = (
        result.get("data", {"items": [], "subtotal": 0, "tax": 0, "total": 0})
        if result["ok"]
        else {"items": [], "subtotal": 0, "tax": 0, "total": 0}
    )

    if not result["ok"]:
        messages.error(request, result.get("error", "Could not load cart."))

    return render(request, "cart.html", {
        "cart":       cart_data,
        "cart_count": sum(int(item.get("quantity", 0)) for item in cart_data.get("items", [])),
        "user":       _get_user(request),
    })

# ─── Checkout & Orders (login required) ──────────────────────────────────────

@_login_required
def checkout_view(request):
    token = _get_token(request)

    # Merge guest cart into user cart after login
    _merge_guest_cart(request)

    cart_result = api.get_cart(token=token)
    if not cart_result["ok"] or not cart_result.get("data", {}).get("items"):
        messages.warning(request, "Your cart is empty.")
        return redirect("menu")

    cart_data = cart_result["data"]

    if request.method == "POST":
        delivery_address = request.POST.get("delivery_address", "").strip()
        special_note     = request.POST.get("special_note", "").strip()

        if not delivery_address:
            messages.error(request, "Please enter a delivery address.")
            return render(request, "checkout.html", {
                "cart": cart_data,
                "cart_count": sum(int(item.get("quantity", 0)) for item in cart_data.get("items", [])),
                "user": _get_user(request),
            })

        order_result = api.place_order(
            token=token,
            delivery_address=delivery_address,
            special_note=special_note
        )
        if not order_result["ok"]:
            messages.error(request, order_result.get("error", "Could not place order."))
            return render(request, "checkout.html", {
                "cart": cart_data,
                "cart_count": sum(int(item.get("quantity", 0)) for item in cart_data.get("items", [])),
                "user": _get_user(request),
            })

        order_data = order_result["data"]
        order_id   = order_data.get("order_id") or order_data.get("id")
        request.session["pending_order_id"] = str(order_id)
        request.session.modified = True

        pay_result = api.initiate_payment(token=token, order_id=order_id)
        if pay_result["ok"]:
            payment_url = pay_result["data"].get("payment_url")
            payment_id  = pay_result["data"].get("payment_id")
            if payment_id:
                request.session["pending_payment_id"] = str(payment_id)
                request.session.modified = True
            if payment_url:
                return redirect(payment_url)

        return redirect("order_confirmation", order_id=order_id)

    return render(request, "checkout.html", {
        "cart":       cart_data,
        "cart_count": sum(int(item.get("quantity", 0)) for item in cart_data.get("items", [])),
        "user":       _get_user(request),
    })

@_login_required
def payment_return_view(request):
    token      = _get_token(request)
    status     = request.GET.get("status", "unknown")
    payment_id = request.GET.get("payment_id") or request.session.get("pending_payment_id")
    order_id   = request.session.get("pending_order_id")
    payment_data = {}

    if payment_id:
        pay_status = api.get_payment_status(token=token, payment_id=payment_id)
        if pay_status["ok"]:
            payment_data = pay_status["data"]
            status = payment_data.get("status", status)

    request.session.pop("pending_payment_id", None)
    request.session.modified = True

    return render(request, "payment_return.html", {
        "payment_status": status,
        "order_id":       order_id,
        "payment_data":   payment_data,
        "cart_count":     0,
        "user":           _get_user(request),
    })

@_login_required
def order_confirmation_view(request, order_id):
    token  = _get_token(request)
    result = api.get_order_detail(token=token, order_id=order_id)
    if not result["ok"]:
        messages.error(request, "Could not load order details.")
        return redirect("order_history")
    request.session.pop("pending_order_id", None)
    request.session.modified = True
    return render(request, "order_confirmation.html", {
        "order":      result["data"],
        "cart_count": 0,
        "user":       _get_user(request),
    })

@_login_required
def order_history_view(request):
    token  = _get_token(request)
    result = api.get_orders(token=token)
    orders = result.get("data", []) if result["ok"] else []
    if not result["ok"]:
        messages.error(request, result.get("error", "Could not load order history."))
    return render(request, "order_history.html", {
        "orders":     orders,
        "cart_count": 0,
        "user":       _get_user(request),
    })

@_login_required
def order_detail_view(request, order_id):
    token  = _get_token(request)
    result = api.get_order_detail(token=token, order_id=order_id)
    if not result["ok"]:
        messages.error(request, "Order not found.")
        return redirect("order_history")
    return render(request, "order_detail.html", {
        "order":      result["data"],
        "cart_count": 0,
        "user":       _get_user(request),
    })

@_login_required
def profile_view(request):
    token = _get_token(request)
    if request.method == "POST":
        data = {
            "name":            request.POST.get("name", "").strip(),
            "email":           request.POST.get("email", "").strip(),
            "default_address": request.POST.get("default_address", "").strip(),
        }
        result = api.update_profile(token=token, data=data)
        if result["ok"]:
            request.session["user_info"] = result["data"].get("user", _get_user(request))
            request.session.modified = True
            messages.success(request, "Profile updated successfully.")
        else:
            messages.error(request, result.get("error", "Update failed."))

    profile_result = api.get_profile(token=token)
    profile = profile_result.get("data", _get_user(request)) if profile_result["ok"] else _get_user(request)

    return render(request, "profile.html", {
        "profile":    profile,
        "cart_count": 0,
        "user":       _get_user(request),
    })