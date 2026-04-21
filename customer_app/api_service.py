"""
api_service.py — Centralized API service layer for Way To Food (WTF)

DEMO MODE: When the real backend is unavailable.

To disable demo mode set in settings.py:
    API_BASE_URL = "http://your-backend.com/api"
    DEMO_MODE = False
"""

import requests
import uuid
import datetime
from django.conf import settings
from django.core.cache import cache

#----- Configuration ------
API_BASE        = "https://test.lazzatt.com"
IMAGE_BASE      = "https://test.lazzatt.com/"
REQUEST_TIMEOUT = 10
DEMO_MODE       = False

# API_BASE        = getattr(settings, "API_BASE_URL", "http://localhost:8000/api")
# REQUEST_TIMEOUT = 10
# DEMO_MODE       = getattr(settings, "DEMO_MODE", True)

#----- HTTP Helpers -----
# These return None on ConnectionError/Timeout to signal "use mock data instead"

def _auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def _safe_error(resp):
    try:
        body = resp.json()
        for field in ("message", "detail", "error", "non_field_errors"):
            if field in body:
                val = body[field]
                return val[0] if isinstance(val, list) else str(val)
        return "An error occurred. Please try again."
    except Exception:
        return f"Server returned status {resp.status_code}."

def _get(url, token=None, params=None):
    if DEMO_MODE:
        return None
    headers = _auth_headers(token) if token else {}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return {"ok": True, "data": resp.json()}
        return {"ok": False, "error": _safe_error(resp), "status": resp.status_code}
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return None  # ← signals: fall back to mock data
    except Exception:
        return {"ok": False, "error": "An unexpected error occurred."}

def _post(url, payload):
    """Send POST request to Lazzatt API. All Lazzatt endpoints use POST."""
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code in (200, 201):
            data = resp.json()
            # Lazzatt wraps all responses in {Success, Message, Data}
            if data.get("Success") == True:
                return {"ok": True, "data": data.get("Data", data)}
            else:
                return {"ok": False, "error": data.get("Message", "Request failed.")}
        return {"ok": False, "error": f"Server error {resp.status_code}"}
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return {"ok": False, "error": "Could not connect to server. Please try again."}
    except Exception as e:
        return {"ok": False, "error": "An unexpected error occurred."}

# def _post(url, payload, token=None):
#     if DEMO_MODE:
#         return None
#     headers = _auth_headers(token) if token else {"Content-Type": "application/json"}
#     try:
#         resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
#         if resp.status_code in (200, 201):
#             return {"ok": True, "data": resp.json()}
#         return {"ok": False, "error": _safe_error(resp), "status": resp.status_code}
#     except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
#         return None  # ← signals: fall back to mock data
#     except Exception:
#         return {"ok": False, "error": "An unexpected error occurred."}

def _put(url, payload, token):
    if DEMO_MODE:
        return None
    try:
        resp = requests.put(url, json=payload, headers=_auth_headers(token), timeout=REQUEST_TIMEOUT)
        if resp.status_code in (200, 204):
            return {"ok": True, "data": resp.json() if resp.content else {}}
        return {"ok": False, "error": _safe_error(resp), "status": resp.status_code}
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return None
    except Exception:
        return {"ok": False, "error": "An unexpected error occurred."}

def _delete(url, token):
    if DEMO_MODE:
        return None
    try:
        resp = requests.delete(url, headers=_auth_headers(token), timeout=REQUEST_TIMEOUT)
        if resp.status_code in (200, 204):
            return {"ok": True, "data": {}}
        return {"ok": False, "error": _safe_error(resp), "status": resp.status_code}
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return None
    except Exception:
        return {"ok": False, "error": "An unexpected error occurred."}

# ---- RESPONSE MAPPERS — Convert Lazzatt field names to internal format ------
# Templates and views use the internal format and never change

def _build_image_url(raw_image):
    """Convert Lazzatt's partial image path to a full URL."""
    if not raw_image or not raw_image.strip():
        return ""
    return IMAGE_BASE + raw_image.strip()

def _map_product(item):
    """Convert one Lazzatt product object to our internal format."""
    return {
        "id":            str(item.get("ProductId", "")),
        "name":          item.get("ProductName", ""),
        "description":   item.get("Description", "").strip(),
        "price":         float(item.get("ProductRate", 0)),
        "image":         _build_image_url(item.get("ProductImage", "")),
        "is_veg":        item.get("IsVeg", True),
        "is_available":  not item.get("IsOutOfStock", False),
        "category":      str(item.get("CuisineType", "")),
        "category_name": "",   # filled in by get_categories() later
        "is_bestseller": item.get("IsBestseller", False),
        "is_chef_recommended": item.get("ChefRecommended", False),
        "is_newly_added": item.get("NewlyAdded", False),
        "rating":        None,   # Lazzatt API doesn't provide ratings
        "review_count":  None,
    }
    
def _map_cart_item(item):
    """Convert one Lazzatt cart item to our internal format."""
    return {
        "id":                   str(item.get("CartDetailID", "")),  # Server-assigned ID
        "item_id":              str(item.get("ProductID", "")),
        "name":                 item.get("ProductName", ""),
        "unit_price":           float(item.get("ProductRate", 0)),
        "discounted_price":     float(item.get("Amount", 0)),
        "quantity":             int(item.get("Quantity", 1)),
        "total_price":          round(float(item.get("Amount", 0)) * int(item.get("Quantity", 1)), 2),
        "image":                _build_image_url(item.get("ProductImage", "")),
        "is_veg":               item.get("IsVeg", True),
        "special_instructions": "",  # Lazzatt doesn't store this field
    }

def _build_cart_from_api(raw):
    """Build our internal cart dict from the full GetCartList response."""
    items = [_map_cart_item(i) for i in raw.get("Data", [])]
    return {
        "items":    items,
        "subtotal": float(raw.get("SubTotal", 0)),
        "tax":      round(float(raw.get("SGST", 0)) + float(raw.get("CGST", 0)), 2),
        "discount": float(raw.get("TotalDiscount", 0)),
        "total":    float(raw.get("TotalBill", 0)),
    }

def _map_order(order):
    """Convert one Lazzatt order object to our internal format."""
    items = []
    for p in order.get("Products", []):
        items.append({
            "name":                 p.get("ProductName", ""),
            "unit_price":           float(p.get("MRP", 0)),
            "quantity":             int(p.get("Quantity", 1)),
            "total_price":          float(p.get("ProductTotalValue", 0)),
            "image":                _build_image_url(p.get("ProductImage", "")),
            "is_veg":               p.get("IsVeg", True),
            "special_instructions": "",
        })

    return {
        "id":             str(order.get("CustomerOrderID", "")),
        "order_id":       str(order.get("CustomerOrderID", "")),
        "order_number":   str(order.get("OrderNumber", "")),
        "status":         order.get("OrderStatus", "Pending"),
        "payment_status": "Paid" if order.get("PaymentMethod") else "Pending",
        "payment_method": str(order.get("PaymentMethod") or ""),
        "total_amount":   float(order.get("TotalValue", 0)),
        "total":          float(order.get("TotalValue", 0)),
        "created_at":     f"{order.get('OrderDate', '')} {order.get('OrderTime', '')}".strip(),
        "items":          items,
        "item_count":     len(items),
        "delivery_address": "",
    }

#------- MOCK DATA --------

_MOCK_CATEGORIES = [
    {"id": "1", "name": "🍕 Starters"},
    {"id": "2", "name": "🍛 Main Course"},
    {"id": "3", "name": "🍞 Breads"},
    {"id": "4", "name": "🍚 Rice & Biryani"},
    {"id": "5", "name": "🥗 Salads"},
    {"id": "6", "name": "🍮 Desserts"},
    {"id": "7", "name": "🥤 Drinks"},
]

# ------- Menu Items -------
"""
Fields explained:
#   id            → unique string, no duplicates
#   name          → dish name shown on card
#   description   → short description shown on card
#   price         → price in rupees (number, not string)
#   category      → must match an "id" from _MOCK_CATEGORIES above
#   category_name → display name of category (can match name above)
#   is_veg        → True = green dot, False = red dot
#   is_available  → False = shows "Unavailable", Add button hidden
#   rating        → optional star rating (e.g. 4.5)
#   review_count  → optional number of reviews
#   image         → optional image URL, leave "" for placeholder emoji
"""

_MOCK_ITEMS = [

    # ---- Starters ----
    {
        "id": "101", "name": "Paneer Tikka",
        "description": "Succulent paneer marinated in spiced yogurt, grilled to perfection in a tandoor.",
        "price": 280, "category": "1", "category_name": "Starters",
        "is_veg": True, "is_available": True, "rating": 4.5, "review_count": 128, "image": "",
    },
    {
        "id": "102", "name": "Veg Spring Rolls",
        "description": "Crispy golden rolls stuffed with seasoned veggies and glass noodles, served with dipping sauce.",
        "price": 180, "category": "1", "category_name": "Starters",
        "is_veg": True, "is_available": True, "rating": 4.2, "review_count": 87, "image": "",
    },
    {
        "id": "103", "name": "Chicken Seekh Kebab",
        "description": "Minced chicken blended with herbs and spices, skewered and chargrilled.",
        "price": 320, "category": "1", "category_name": "Starters",
        "is_veg": False, "is_available": True, "rating": 4.7, "review_count": 210, "image": "",
    },
    {
        "id": "104", "name": "Hara Bhara Kebab",
        "description": "Pan-fried patties made with spinach, peas, and cottage cheese — healthy and delicious.",
        "price": 220, "category": "1", "category_name": "Starters",
        "is_veg": True, "is_available": True, "rating": 4.3, "review_count": 65, "image": "",
    },

    # --- Main Course ---
    {
        "id": "201", "name": "Butter Chicken",
        "description": "Tender chicken in a rich, creamy tomato-butter gravy — India's most loved dish.",
        "price": 380, "category": "2", "category_name": "Main Course",
        "is_veg": False, "is_available": True, "rating": 4.8, "review_count": 342, "image": "",
    },
    {
        "id": "202", "name": "Malai Kofta",
        "description": "Soft cottage cheese and potato dumplings in a velvety cashew-cream sauce.",
        "price": 340, "category": "2", "category_name": "Main Course",
        "is_veg": True, "is_available": True, "rating": 4.6, "review_count": 156, "image": "",
    },
    {
        "id": "203", "name": "Dal Makhani",
        "description": "Slow-cooked black lentils simmered overnight with butter and cream.",
        "price": 260, "category": "2", "category_name": "Main Course",
        "is_veg": True, "is_available": True, "rating": 4.5, "review_count": 198, "image": "",
    },
    {
        "id": "204", "name": "Kadai Paneer",
        "description": "Paneer and peppers tossed in a bold, aromatic kadai masala.",
        "price": 310, "category": "2", "category_name": "Main Course",
        "is_veg": True, "is_available": False, "rating": 4.4, "review_count": 112, "image": "",
    },
    {
        "id": "205", "name": "Mutton Rogan Josh",
        "description": "Slow-braised mutton in a fragrant Kashmiri spice blend — a royal classic.",
        "price": 460, "category": "2", "category_name": "Main Course",
        "is_veg": False, "is_available": True, "rating": 4.9, "review_count": 278, "image": "",
    },

    # ---- Breads ----
    {
        "id": "301", "name": "Garlic Naan",
        "description": "Fluffy leavened bread slathered with garlic butter, baked in a clay oven.",
        "price": 60, "category": "3", "category_name": "Breads",
        "is_veg": True, "is_available": True, "rating": 4.6, "review_count": 430, "image": "",
    },
    {
        "id": "302", "name": "Butter Roti",
        "description": "Whole wheat flatbread lightly coated with fresh butter.",
        "price": 35, "category": "3", "category_name": "Breads",
        "is_veg": True, "is_available": True, "rating": 4.3, "review_count": 215, "image": "",
    },
    {
        "id": "303", "name": "Laccha Paratha",
        "description": "Multi-layered flaky paratha with a beautiful crispy texture.",
        "price": 70, "category": "3", "category_name": "Breads",
        "is_veg": True, "is_available": True, "rating": 4.5, "review_count": 167, "image": "",
    },

    # --- Rice & Biryani ---
    {
        "id": "401", "name": "Veg Biryani",
        "description": "Fragrant basmati rice layered with seasonal vegetables and whole spices.",
        "price": 240, "category": "4", "category_name": "Rice & Biryani",
        "is_veg": True, "is_available": True, "rating": 4.4, "review_count": 189, "image": "",
    },
    {
        "id": "402", "name": "Chicken Biryani",
        "description": "Aromatic long-grain rice slow-cooked with marinated chicken and saffron.",
        "price": 320, "category": "4", "category_name": "Rice & Biryani",
        "is_veg": False, "is_available": True, "rating": 4.8, "review_count": 512, "image": "",
    },
    {
        "id": "403", "name": "Jeera Rice",
        "description": "Steamed basmati rice tempered with cumin seeds and ghee.",
        "price": 120, "category": "4", "category_name": "Rice & Biryani",
        "is_veg": True, "is_available": True, "rating": 4.2, "review_count": 98, "image": "",
    },
    
    # --- Salads ---
    {
        "id": "501", "name": "Garden Fresh Salad",
        "description": "Crisp lettuce, cucumber, tomatoes and carrots tossed in a light lemon dressing.",
        "price": 150, "category": "5", "category_name": "Salads",
        "is_veg": True, "is_available": True, "rating": 4.1, "review_count": 43, "image": "",
    },
    {
        "id": "502", "name": "Fruit Chaat",
        "description": "Seasonal fruits tossed in tangy chaat masala and a squeeze of fresh lime.",
        "price": 120, "category": "5", "category_name": "Salads",
        "is_veg": True, "is_available": True, "rating": 4.3, "review_count": 67, "image": "",
    },

    # ---- Desserts ----
    {
        "id": "601", "name": "Gulab Jamun",
        "description": "Soft milk-solid dumplings soaked in rose-flavoured sugar syrup. Served warm.",
        "price": 120, "category": "6", "category_name": "Desserts",
        "is_veg": True, "is_available": True, "rating": 4.7, "review_count": 320, "image": "",
    },
    {
        "id": "602", "name": "Rasgulla",
        "description": "Light, spongy cottage cheese balls in a light sugar syrup. A Bengali classic.",
        "price": 100, "category": "6", "category_name": "Desserts",
        "is_veg": True, "is_available": True, "rating": 4.5, "review_count": 145, "image": "",
    },
    {
        "id": "603", "name": "Kulfi Falooda",
        "description": "Dense, creamy Indian ice cream served with vermicelli and rose syrup.",
        "price": 160, "category": "6", "category_name": "Desserts",
        "is_veg": True, "is_available": True, "rating": 4.6, "review_count": 201, "image": "",
    },

    # ── Drinks ──
    {
        "id": "701", "name": "Mango Lassi",
        "description": "Thick yogurt blended with fresh Alphonso mango pulp and a pinch of cardamom.",
        "price": 120, "category": "7", "category_name": "Drinks",
        "is_veg": True, "is_available": True, "rating": 4.8, "review_count": 390, "image": "",
    },
    {
        "id": "702", "name": "Masala Chaas",
        "description": "Chilled spiced buttermilk with roasted cumin and fresh coriander.",
        "price": 60, "category": "7", "category_name": "Drinks",
        "is_veg": True, "is_available": True, "rating": 4.4, "review_count": 175, "image": "",
    },
    {
        "id": "703", "name": "Fresh Lime Soda",
        "description": "Zesty lime squeezed over chilled soda water — sweet or salted.",
        "price": 80, "category": "7", "category_name": "Drinks",
        "is_veg": True, "is_available": True, "rating": 4.3, "review_count": 210, "image": "",
    },
]

# ----- In-memory stores (resets on server restart — fine for demo) -----

# Cart store: { token: { cart_item_id: { id, item_id, name, unit_price, quantity, ... } } }
_MOCK_CARTS = {}

# Order store: { token: [ order_dict, ... ] }
_MOCK_ORDERS = {}

# ---- Internal helpers ----

def _get_item_by_id(item_id):
    """Find a mock item by its id."""
    return next((i for i in _MOCK_ITEMS if i["id"] == str(item_id)), None)

def _build_cart_response(token):
    """Build a cart response dict from the in-memory cart store."""
    cart = _MOCK_CARTS.get(token, {})
    items = []
    subtotal = 0
    for ci in cart.values():
        total_price = ci["unit_price"] * ci["quantity"]
        subtotal += total_price
        items.append({
            "id":                   ci["id"],
            "item_id":              ci["item_id"],
            "name":                 ci["name"],
            "unit_price":           ci["unit_price"],
            "quantity":             ci["quantity"],
            "total_price":          round(total_price, 2),
            "special_instructions": ci.get("special_instructions", ""),
            "image":                ci.get("image", ""),
        })
    tax   = round(subtotal * 0.05, 2)   # 5% GST — change 0.05 to adjust
    total = round(subtotal + tax, 2)
    return {
        "items":    items,
        "subtotal": round(subtotal, 2),
        "tax":      tax,
        "total":    total,
    }

def _mock_token():
    return "demo-token-" + str(uuid.uuid4())[:8]

# --- API Functions — each tries real API first, falls back to mock on failure ---

# ---- Authentication ----

# def login(phone, password=None):
#     """POST /auth/login/"""
#     payload = {"phone": phone}
#     if password:
#         payload["password"] = password

#     result = _post(f"{API_BASE}/auth/login/", payload)
#     if result is not None:
#         return result

#     # DEMO FALLBACK — accepts any credentials
#     token = _mock_token()
#     return {"ok": True, "data": {
#         "token": token,
#         "user": {
#             "id":    "demo-001",
#             "name":  "Demo Customer",
#             "phone": phone,
#             "email": "demo@waytofood.com",
#         }
#     }}

def login(phone, password=None):
    """Login via Lazzatt /Api/Login endpoint."""
    result = _post(f"{API_BASE}/Api/Login", {
        "CustomerMobile": phone,
        "Password": password or "",
        "AuthenticationType": 0
    })

    if not result["ok"]:
        # result["error"] already has the Message from Lazzatt
        return result

    raw = result["data"]
    customer_id = raw.get("CustomerId", 0)

    # Check — even if Success=true, CustomerId=0 means something is wrong
    if not customer_id:
        return {"ok": False, "error": "Login failed. Please check your credentials."}

    return {"ok": True, "data": {
        "token": str(customer_id),   # CustomerId as  session token
        "user": {
            "id":    str(customer_id),
            "name":  raw.get("CustomerName", "").strip(),
            "phone": raw.get("CustomerMobile", "").strip(),
            "email": raw.get("Email", "").strip(),
        }
    }}

def register(name, phone, email, password):
    """Register a new customer via Lazzatt /Api/CreateCustomer."""
    result = _post(f"{API_BASE}/Api/CreateCustomer", {
        "CustomerName":       name,
        "Email":              email,
        "AuthenticationType": 1
    })

    if not result["ok"]:
        return result

    # After creating, log them in immediately
    return login(phone=phone, password=password)

# def register(name, phone, email, password):
#     """POST /auth/register/"""
#     result = _post(f"{API_BASE}/auth/register/", {
#         "name": name, "phone": phone, "email": email, "password": password
#     })
#     if result is not None:
#         return result

#     # DEMO FALLBACK
#     token = _mock_token()
#     return {"ok": True, "data": {
#         "token": token,
#         "user": {
#             "id":    "demo-" + str(uuid.uuid4())[:6],
#             "name":  name,
#             "phone": phone,
#             "email": email,
#         }
#     }}

def get_profile(token):
    """Fetch customer details using CustomerID."""
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Not logged in."}

    result = _post(f"{API_BASE}/Api/GetCustomerDetails", {
        "CustomerID": token
    })
    if not result["ok"]:
        return result

    raw = result["data"]
    return {"ok": True, "data": {
        "id":              str(raw.get("CustomerId", "")),
        "name":            raw.get("CustomerName", "").strip(),
        "phone":           raw.get("CustomerMobile", "").strip(),
        "email":           raw.get("Email", "").strip(),
        "default_address": "",
    }}

def update_profile(token, data):
    """Update customer profile via Lazzatt /Api/UpdateProfile."""
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Not logged in."}

    result = _post(f"{API_BASE}/Api/UpdateProfile", {
        "CustomerName":   data.get("name", ""),
        "Email":          data.get("email", ""),
        "CustomerMobile": data.get("phone", ""),
    })
    if not result["ok"]:
        return result

    return {"ok": True, "data": {"user": data}}

def send_otp(phone):
    """POST /auth/send-otp/"""
    result = _post(f"{API_BASE}/auth/send-otp/", {"phone": phone})
    if result is not None:
        return result
    # DEMO FALLBACK — pretend OTP was sent
    return {"ok": True, "data": {"message": "OTP sent successfully"}}

def verify_otp(phone, otp):
    """POST /auth/verify-otp/"""
    result = _post(f"{API_BASE}/auth/verify-otp/", {"phone": phone, "otp": otp})
    if result is not None:
        return result
    # DEMO FALLBACK — accept any OTP
    token = _mock_token()
    return {"ok": True, "data": {
        "token": token,
        "user": {
            "id":    "demo-001",
            "name":  "Demo Customer",
            "phone": phone,
            "email": "demo@waytofood.com",
        }
    }}

# ---- Menu & Categories ----

# def get_categories(token=None):
#     """GET /menu/categories/"""
#     result = _get(f"{API_BASE}/menu/categories/", token=token)
#     if result is not None:
#         return result

#     # DEMO FALLBACK
#     return {"ok": True, "data": _MOCK_CATEGORIES}

def get_categories(token=None):
    """Fetch product categories from Lazzatt."""
    result = _post(f"{API_BASE}/Api/GetProductType", {})
    if not result["ok"]:
        return result

    categories = [
        {
            "id":   str(cat["ProductTypeID"]),
            "name": cat["ProductTypeName"]
        }
        for cat in result["data"]
    ]
    return {"ok": True, "data": categories}

def get_menu_items(token=None, category_id=None, search=None):
    """Fetch menu items from Lazzatt API."""

    if search:
        result = _post(f"{API_BASE}/Api/GetSearchProduct", {
            "SearchName": search,
            "CustomerId": 0
        })
        if result["ok"]:
            return {"ok": True, "data": [_map_product(p) for p in result["data"]]}
        return {"ok": False, "error": result.get("error", "Search failed.")}

    result = _post(f"{API_BASE}/Api/GetProduct", {
        "VeganType": "0",
        "CuisineType": "1"
    })
    if not result["ok"]:
        return {"ok": False, "error": result.get("error", "Could not load menu.")}

    items = [_map_product(p) for p in result["data"]]

    # Store in cache for 5 minutes so item_detail doesn't need to re-fetch
    cache.set("wtf_all_products", result["data"], timeout=300)

    return {"ok": True, "data": items}

# def get_menu_items(token=None, category_id=None, search=None):
#     """GET /menu/items/?category=&search="""
#     params = {}
#     if category_id:
#         params["category"] = category_id
#     if search:
#         params["search"] = search

#     result = _get(f"{API_BASE}/menu/items/", token=token, params=params)
#     if result is not None:
#         return result

#     # DEMO FALLBACK — filter mock items locally
#     items = _MOCK_ITEMS[:]
#     if category_id:
#         items = [i for i in items if i["category"] == str(category_id)]
#     if search:
#         s = search.lower()
#         items = [
#             i for i in items
#             if s in i["name"].lower()
#             or s in i["description"].lower()
#             or s in i["category_name"].lower()
#         ]
#     return {"ok": True, "data": items}

def get_menu_item_detail(item_id, token=None):
    """
    Fetch a single product by ID.
    Uses cached product list if available — avoids a full API call on every detail page visit.
    Falls back to a fresh API call if cache is empty.
    """
    # Try cache first
    cached_products = cache.get("wtf_all_products")

    if cached_products:
        for raw_item in cached_products:
            if str(raw_item.get("ProductId")) == str(item_id):
                return {"ok": True, "data": _map_product(raw_item)}

    # Cache miss — fetch fresh from API
    result = _post(f"{API_BASE}/Api/GetProduct", {
        "VeganType": "0",
        "CuisineType": "1"
    })
    if not result["ok"]:
        return {"ok": False, "error": "Could not load item details."}

    # Refresh cache while we have the data
    cache.set("wtf_all_products", result["data"], timeout=300)

    for raw_item in result["data"]:
        if str(raw_item.get("ProductId")) == str(item_id):
            return {"ok": True, "data": _map_product(raw_item)}

    return {"ok": False, "error": "Item not found."}

# def get_menu_item_detail(item_id, token=None):
#     """GET /menu/items/{id}/"""
#     result = _get(f"{API_BASE}/menu/items/{item_id}/", token=token)
#     if result is not None:
#         return result

#     # DEMO FALLBACK
#     item = _get_item_by_id(item_id)
#     if item:
#         return {"ok": True, "data": item}
#     return {"ok": False, "error": "Item not found."}

# --- Cart ------

def _post_full(url, payload):
    """
    Same as _post() but returns the FULL response body, not just Data.
    Needed for endpoints like GetCartList where totals are at the top level.
    """
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code in (200, 201):
            data = resp.json()
            if data.get("Success") == True:
                return {"ok": True, "data": data}   # Return full response, not just Data
            else:
                return {"ok": False, "error": data.get("Message", "Request failed.")}
        return {"ok": False, "error": f"Server error {resp.status_code}"}
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return {"ok": False, "error": "Could not connect to server. Please try again."}
    except Exception:
        return {"ok": False, "error": "An unexpected error occurred."}

def get_cart(token):
    """Fetch cart for logged-in user using CustomerID."""
    if not token or token.startswith("guest-"):
        # Guest users have no server-side cart — return empty
        return {"ok": True, "data": {"items": [], "subtotal": 0, "tax": 0, "total": 0}}

    result = _post_full(f"{API_BASE}/Api/GetCartList", {
        "CustomerID": token,
        "IsRedeemPoint": False
    })
    if not result["ok"]:
        return result

    return {"ok": True, "data": _build_cart_from_api(result["data"])}

# def get_cart(token):
#     """GET /cart/"""
#     result = _get(f"{API_BASE}/cart/", token=token)
#     if result is not None:
#         return result

#     # DEMO FALLBACK
#     return {"ok": True, "data": _build_cart_response(token)}

# def add_to_cart(token, item_id, quantity, special_instructions=""):
#     """POST /cart/add/"""
#     result = _post(f"{API_BASE}/cart/add/", {
#         "item_id": item_id,
#         "quantity": quantity,
#         "special_instructions": special_instructions,
#     }, token=token)
#     if result is not None:
#         return result

#     # DEMO FALLBACK
#     item = _get_item_by_id(item_id)
#     if not item:
#         return {"ok": False, "error": "Item not found."}

#     cart = _MOCK_CARTS.setdefault(token, {})

#     # If item already in cart, increase quantity
#     existing = next((ci for ci in cart.values() if ci["item_id"] == str(item_id)), None)
#     if existing:
#         existing["quantity"] += quantity
#         if special_instructions:
#             existing["special_instructions"] = special_instructions
#     else:
#         cart_item_id = str(uuid.uuid4())[:8]
#         cart[cart_item_id] = {
#             "id":                   cart_item_id,
#             "item_id":              str(item_id),
#             "name":                 item["name"],
#             "unit_price":           item["price"],
#             "quantity":             quantity,
#             "special_instructions": special_instructions,
#             "image":                item.get("image", ""),
#         }

#     return {"ok": True, "data": _build_cart_response(token)}

def add_to_cart(token, item_id, quantity, special_instructions=""):
    """Add item to cart. Requires logged-in user (CustomerID)."""
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Please log in to add items to cart."}

    # First we need the item price — fetch it from the product list
    # Lazzatt's AddToCart needs the Amount (price) in the body
    product_result = _post(f"{API_BASE}/Api/GetProduct", {
        "VeganType": "0",
        "CuisineType": "1"
    })

    item_price = 0
    if product_result["ok"]:
        for p in product_result["data"]:
            if str(p.get("ProductId")) == str(item_id):
                item_price = float(p.get("ProductRate", 0))
                break

    result = _post(f"{API_BASE}/Api/AddToCart", {
        "CustomerID": token,
        "Quantity":   str(quantity),
        "ProductID":  str(item_id),
        "Amount":     item_price
    })

    if not result["ok"]:
        return result

    # Return updated cart after adding
    return get_cart(token)

def update_cart_item(token, cart_item_id, quantity):
    """Update quantity of a cart item using CartDetailID."""
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Please log in."}

    result = _post(f"{API_BASE}/Api/UpdateCart", {
        "CustomerID":   token,
        "CartDetailID": str(cart_item_id),
        "Quantity":     str(quantity)
    })

    if not result["ok"]:
        return result

    return get_cart(token)

# def update_cart_item(token, cart_item_id, quantity):
#     """PUT /cart/items/{id}/"""
#     result = _put(
#         f"{API_BASE}/cart/items/{cart_item_id}/",
#         {"quantity": quantity},
#         token=token
#     )
#     if result is not None:
#         return result

#     # DEMO FALLBACK
#     cart = _MOCK_CARTS.get(token, {})
#     if cart_item_id in cart:
#         cart[cart_item_id]["quantity"] = quantity
#         return {"ok": True, "data": _build_cart_response(token)}
#     return {"ok": False, "error": "Cart item not found."}

def remove_cart_item(token, cart_item_id):
    """Remove a cart item using CartDetailID."""
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Please log in."}

    result = _post(f"{API_BASE}/Api/RemoveCart", {
        "CustomerID":   token,
        "CartDetailID": str(cart_item_id)
    })

    if not result["ok"]:
        return result

    return get_cart(token)

# def remove_cart_item(token, cart_item_id):
#     """DELETE /cart/items/{id}/"""
#     result = _delete(f"{API_BASE}/cart/items/{cart_item_id}/", token=token)
#     if result is not None:
#         return result

#     # DEMO FALLBACK
#     cart = _MOCK_CARTS.get(token, {})
#     cart.pop(cart_item_id, None)
#     return {"ok": True, "data": _build_cart_response(token)}

def clear_cart(token):
    """Clear cart by removing all items one by one — Lazzatt has no bulk clear endpoint."""
    if not token or token.startswith("guest-"):
        return {"ok": True, "data": {"items": [], "subtotal": 0, "tax": 0, "total": 0}}

    cart_result = get_cart(token)
    if not cart_result["ok"]:
        return cart_result

    items = cart_result["data"].get("items", [])
    for item in items:
        _post(f"{API_BASE}/Api/RemoveCart", {
            "CustomerID":   token,
            "CartDetailID": str(item["id"])
        })
        # We ignore individual errors here — best effort clear

    return {"ok": True, "data": {"items": [], "subtotal": 0, "tax": 0, "total": 0}}

# --- Orders ----

def place_order(token, delivery_address, special_note=""):
    """
    Place order via Lazzatt.
    Step 1: Save delivery address via AddAddress → get AddressID
    Step 2: Call OrderPlaced with that AddressID
    """
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Please log in to place an order."}

    # Step 1 — Save address and get AddressID
    address_result = _post(f"{API_BASE}/Api/AddAddress", {
        "CustomerID":   token,
        "FriendlyName": "Delivery Address",
        "Address1":     delivery_address,
        "Address2":     "",
        "Landmark":     "",
        "PostalCode":   "",
        "AreaID":       "1",       # Default area — update once GetArea is integrated
        "Latitude":     "0",
        "Longitude":    "0",
        "City":         "",
        "State":        "",
        "Country":      "India",
        "AddressType":  "Home"
    })

    address_id = 0
    if address_result["ok"] and isinstance(address_result["data"], dict):
        address_id = address_result["data"].get("AddressID", 0)

    # Step 2 — Place order
    result = _post(f"{API_BASE}/Api/OrderPlaced", {
        "CustomerId":           int(token),
        "AddressID":            address_id,
        "PaymentMethod":        2,          # 2 = Online payment
        "OrderType":            1,          # 1 = Delivery
        "IsRedeemPoint":        False,
        "Remarks":              special_note,
        "DeliveryCharges":      0,
        "PorterOrderID":        0,
        "TrackingURL":          "",
        "PickupTime":           0,          # Must be integer, not string
        "RequestPorterOrderID": 0
    })

    if not result["ok"]:
        return result

    raw = result["data"]
    order_id = raw.get("CustomerOrderID") or raw.get("OrderId") or str(uuid.uuid4())[:8]

    return {"ok": True, "data": {
        "id":               str(order_id),
        "order_id":         str(order_id),
        "status":           "Confirmed",
        "total_amount":     0,
        "total":            0,
        "delivery_address": delivery_address,
    }}

# def place_order(token, delivery_address, special_note=""):
#     """POST /orders/"""
#     result = _post(f"{API_BASE}/orders/", {
#         "delivery_address": delivery_address,
#         "special_note":     special_note,
#     }, token=token)
#     if result is not None:
#         return result

#     # DEMO FALLBACK
#     cart_data = _build_cart_response(token)
#     if not cart_data["items"]:
#         return {"ok": False, "error": "Cart is empty."}

#     order_id = "WTF-" + str(uuid.uuid4())[:6].upper()
#     now      = datetime.datetime.now()

#     order = {
#         "id":                order_id,
#         "order_id":          order_id,
#         "status":            "Confirmed",
#         "payment_status":    "Pending",
#         "items":             [
#             {**ci, "total_price": ci["unit_price"] * ci["quantity"]}
#             for ci in cart_data["items"]
#         ],
#         "subtotal":          cart_data["subtotal"],
#         "tax":               cart_data["tax"],
#         "total_amount":      cart_data["total"],
#         "total":             cart_data["total"],
#         "delivery_address":  delivery_address,
#         "special_note":      special_note,
#         "created_at":        now.strftime("%d %b %Y, %I:%M %p"),
#         "estimated_delivery": "30–45 minutes",
#         "item_count":        len(cart_data["items"]),
#     }

#     # Save order and clear the cart
#     _MOCK_ORDERS.setdefault(token, []).insert(0, order)
#     _MOCK_CARTS[token] = {}

#     return {"ok": True, "data": order}

def get_orders(token):
    """Fetch order history for logged-in customer."""
    if not token or token.startswith("guest-"):
        return {"ok": True, "data": []}

    result = _post(f"{API_BASE}/Api/GetOrder", {
        "CustomerId": int(token)
    })
    if not result["ok"]:
        return result

    orders = [_map_order(o) for o in result["data"]]
    return {"ok": True, "data": orders}

# def get_orders(token):
#     """GET /orders/"""
#     result = _get(f"{API_BASE}/orders/", token=token)
#     if result is not None:
#         return result

#     # DEMO FALLBACK — show in-session orders, or sample history if none
#     orders = _MOCK_ORDERS.get(token, [])

#     if not orders:
#         # ── STEP 3 (optional): Edit these sample past orders ──────────────
#         orders = [
#             {
#                 "id": "WTF-DEMO01", "order_id": "WTF-DEMO01",
#                 "status": "Delivered", "payment_status": "Paid",
#                 "total_amount": 680, "total": 680,
#                 "created_at": "10 Jan 2025, 07:30 PM",
#                 "item_count": 3,
#                 "items": [
#                     {"name": "Butter Chicken", "unit_price": 380, "quantity": 1, "total_price": 380},
#                     {"name": "Garlic Naan",    "unit_price": 60,  "quantity": 2, "total_price": 120},
#                     {"name": "Gulab Jamun",    "unit_price": 120, "quantity": 1, "total_price": 120},
#                 ],
#                 "delivery_address": "12, MG Road, Bengaluru",
#             },
#             {
#                 "id": "WTF-DEMO02", "order_id": "WTF-DEMO02",
#                 "status": "Delivered", "payment_status": "Paid",
#                 "total_amount": 420, "total": 420,
#                 "created_at": "05 Jan 2025, 01:15 PM",
#                 "item_count": 2,
#                 "items": [
#                     {"name": "Chicken Biryani", "unit_price": 320, "quantity": 1, "total_price": 320},
#                     {"name": "Mango Lassi",     "unit_price": 120, "quantity": 1, "total_price": 120},
#                 ],
#                 "delivery_address": "12, MG Road, Bengaluru",
#             },
#         ]
#         # ---- End of sample orders ----

#     return {"ok": True, "data": orders}

def get_order_detail(token, order_id):
    """
    Fetch a single order by CustomerOrderID.
    Lazzatt has no single-order endpoint, so we fetch all orders and filter.
    """
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Not logged in."}

    result = _post(f"{API_BASE}/Api/GetOrder", {
        "CustomerId": int(token)
    })
    if not result["ok"]:
        return result

    for raw_order in result["data"]:
        if str(raw_order.get("CustomerOrderID")) == str(order_id):
            return {"ok": True, "data": _map_order(raw_order)}

    return {"ok": False, "error": "Order not found."}

# def get_order_detail(token, order_id):
#     """GET /orders/{id}/"""
#     result = _get(f"{API_BASE}/orders/{order_id}/", token=token)
#     if result is not None:
#         return result

#     # DEMO FALLBACK — check in-session orders first
#     for order in _MOCK_ORDERS.get(token, []):
#         if order["id"] == str(order_id):
#             return {"ok": True, "data": order}

#     # Then check the static demo orders
#     _demo_orders = {
#         "WTF-DEMO01": {
#             "id": "WTF-DEMO01", "order_id": "WTF-DEMO01",
#             "status": "Delivered", "payment_status": "Paid", "payment_method": "UPI",
#             "total_amount": 680, "total": 680, "subtotal": 620, "tax": 31,
#             "created_at": "10 Jan 2025, 07:30 PM",
#             "estimated_delivery": "Delivered",
#             "delivery_address": "12, MG Road, Bengaluru, Karnataka - 560001",
#             "items": [
#                 {"name": "Butter Chicken", "unit_price": 380, "quantity": 1, "total_price": 380, "special_instructions": ""},
#                 {"name": "Garlic Naan",    "unit_price": 60,  "quantity": 2, "total_price": 120, "special_instructions": "Extra butter"},
#                 {"name": "Gulab Jamun",    "unit_price": 120, "quantity": 1, "total_price": 120, "special_instructions": ""},
#             ],
#         },
#         "WTF-DEMO02": {
#             "id": "WTF-DEMO02", "order_id": "WTF-DEMO02",
#             "status": "Delivered", "payment_status": "Paid", "payment_method": "Credit Card",
#             "total_amount": 420, "total": 420, "subtotal": 400, "tax": 20,
#             "created_at": "05 Jan 2025, 01:15 PM",
#             "estimated_delivery": "Delivered",
#             "delivery_address": "12, MG Road, Bengaluru, Karnataka - 560001",
#             "items": [
#                 {"name": "Chicken Biryani", "unit_price": 320, "quantity": 1, "total_price": 320, "special_instructions": "Extra raita"},
#                 {"name": "Mango Lassi",     "unit_price": 120, "quantity": 1, "total_price": 120, "special_instructions": ""},
#             ],
#         },
#     }

#     if str(order_id) in _demo_orders:
#         return {"ok": True, "data": _demo_orders[str(order_id)]}
#     return {"ok": False, "error": "Order not found."}

# ---- Payment ----

def initiate_payment(token, order_id):
    """
    Lazzatt handles payment externally.
    We skip the gateway and go straight to confirmation.
    """
    return {"ok": True, "data": {
        "payment_id":  None,
        "payment_url": None,
        "order_id":    order_id,
    }}

# def initiate_payment(token, order_id):
#     """POST /payments/initiate/"""
#     result = _post(f"{API_BASE}/payments/initiate/", {"order_id": order_id}, token=token)
#     if result is not None:
#         return result

#     # DEMO FALLBACK — skip gateway, go straight to confirmation
#     payment_id = "PAY-" + str(uuid.uuid4())[:8].upper()
#     return {"ok": True, "data": {
#         "payment_id":  payment_id,
#         "payment_url": None,     # None = no redirect, goes to confirmation page
#         "order_id":    order_id,
#     }}

def get_payment_status(token, payment_id):
    """GET /payments/{id}/status/"""
    result = _get(f"{API_BASE}/payments/{payment_id}/status/", token=token)
    if result is not None:
        return result

    # DEMO FALLBACK — always return success
    return {"ok": True, "data": {
        "payment_id": payment_id,
        "status":     "success",
        "message":    "Payment successful (demo mode)",
    }}