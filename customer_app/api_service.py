import requests
import uuid
from django.core.cache import cache

#----- Configuration ------
API_BASE        = "https://test.lazzatt.com"
IMAGE_BASE      = "https://test.lazzatt.com/"
REQUEST_TIMEOUT = 10
DEMO_MODE       = False

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

def _build_image_url(raw_image):
    """Convert Lazzatt's partial image path to a full URL."""
    if not raw_image or not raw_image.strip():
        return ""
    return IMAGE_BASE + raw_image.strip()

# ---- RESPONSE MAPPERS — Convert Lazzatt field names to internal format ------

def _map_product(item):
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
    items = [_map_cart_item(i) for i in raw.get("Data", [])]
    return {
        "items":    items,
        "subtotal": float(raw.get("SubTotal", 0)),
        "tax":      round(float(raw.get("SGST", 0)) + float(raw.get("CGST", 0)), 2),
        "discount": float(raw.get("TotalDiscount", 0)),
        "total":    float(raw.get("TotalBill", 0)),
    }

def _map_order(order):
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

    # Build payload — if category selected, use GetPagerProduct for that type
    if category_id:
        result = _post(f"{API_BASE}/Api/GetPagerProduct", {
            "VeganType": 0,
            "CuisineType": 1,
            "PageSize": 100,
            "PageNumber": 1,
            "ProductTypeId": int(category_id)
        })
    else:
        result = _post(f"{API_BASE}/Api/GetProduct", {
            "VeganType": "0",
            "CuisineType": "1"
        })

    if not result["ok"]:
        return {"ok": False, "error": result.get("error", "Could not load menu.")}

    items = [_map_product(p) for p in result["data"]]
    cache.set("wtf_all_products", result["data"], timeout=300)
    return {"ok": True, "data": items}

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

# ---- Cart -----

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

def add_to_cart(token, item_id, quantity, special_instructions=""):
    """Add item to cart. Requires logged-in user (CustomerID)."""
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Please log in to add items to cart."}

    # First, the item price — fetch it from the product list
    # Lazzatt's AddToCart needs the Amount (price) in the body
    cached = cache.get("wtf_all_products")
    raw_products = cached if cached else []

    if not raw_products:
        product_result = _post(f"{API_BASE}/Api/GetProduct", {
            "VeganType": "0",
            "CuisineType": "1"
        })
        if product_result["ok"]:
            raw_products = product_result["data"]
            cache.set("wtf_all_products", raw_products, timeout=300)

    item_price = 0
    for p in raw_products:
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

    return {"ok": True, "data": {"items": [], "subtotal": 0, "tax": 0, "total": 0}}

# --- Orders ----

def place_order(token, delivery_address, special_note=""):
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

def get_payment_status(token, payment_id):
    """Lazzatt handles payment externally — no status endpoint available."""
    return {"ok": True, "data": {"status": "success"}}