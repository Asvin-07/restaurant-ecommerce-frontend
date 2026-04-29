import requests
from django.core.cache import cache

#----- Configuration ------
API_BASE        = "https://test.lazzatt.com"
IMAGE_BASE      = "https://test.lazzatt.com/upload/"
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
    except Exception:
        return {"ok": False, "error": "An unexpected error occurred."}

def _build_image_url(raw_image):
    """Convert Lazzatt's partial image path to a full URL."""
    if not raw_image or not raw_image.strip():
        return ""
    return IMAGE_BASE + raw_image.strip()

# ---- RESPONSE MAPPERS - Convert Lazzatt field names to internal format ------

def _map_banner(item):
    return {
        "id":    item.get("BannerId"),
        "image": _build_image_url(item.get("BannerImage", "")),
        "link":  "#"
    }

def _map_offer(item):
    return {
        "id":      item.get("OfferID"),
        "image":   _build_image_url(item.get("OfferImage", "")),
        "title":   item.get("OfferTitle", ""),
        "content": item.get("OfferContent", "")
    }

def _map_live_order(item):
    tracking = item.get("TrackingURL")
    return {
        "id":           item.get("CustomerOrderID"),
        "order_number": item.get("OrderNumber"),
        "tracking_url": tracking if tracking and tracking != "NA" else None,
        "amount":       float(item.get("OrderAmount", 0)),
    }

def _map_redeem_balance(data):
    return {
        "balance":        data.get("BalanceRedeem", 0),
        "max_redeemable": data.get("MaxRedeemablePoints", 0)
    }

def _map_loyalty_program(data):
    return {
        "title":      data.get("HeaderTitle", ""),
        "info_title": data.get("InfoTitle", ""),
        "conditions": data.get("UseConditions", ""),
        "tiers": [
            {
                "type":    tier.get("CustomerType"),
                "title":   tier.get("Title"),
                "image":   _build_image_url(tier.get("BannerImage", "")),
                "details": tier.get("ProgramDetail", "")
            }
            for tier in data.get("Data", [])
        ]
    }

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

    # Check - even if Success=true, CustomerId=0 means something is wrong
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
        "CustomerMobile":     phone,
        "Password":           password,
        "AuthenticationType": 1
    })

    if not result["ok"]:
        return result

    # Attempt login immediately after registration
    login_result = login(phone=phone, password=password)
    if login_result["ok"]:
        return login_result

    # If login fails after registration, account was created but login failed
    # This typically means the backend doesn't accept password via CreateCustomer
    return {"ok": False, "error": "Account created but could not log in automatically. Please try logging in manually once your account is activated."}

# ---- Address ----

def get_saved_addresses(token):
    """Fetch customer's saved delivery addresses."""
    if not token or token.startswith("guest-"):
        return {"ok": True, "data": []}
    result = _post(f"{API_BASE}/Api/GetNearestAddresses", {
        "CustomerID": token
    })
    if not result["ok"]:
        return {"ok": True, "data": []}
    data = result["data"]
    if isinstance(data, list):
        return {"ok": True, "data": [
            {
                "id":           str(a.get("AddressID", a.get("AddressId", ""))),
                "friendly_name": a.get("FriendlyName", "Home"),
                "address1":     a.get("Address1", ""),
                "address2":     a.get("Address2", ""),
                "landmark":     a.get("Landmark", ""),
                "city":         a.get("City", ""),
                "state":        a.get("State", ""),
                "postal_code":  a.get("PostalCode", ""),
                "address_type": a.get("AddressType", "Home"),
                "area_id":      str(a.get("AreaID", a.get("AreaId", "1"))),
            }
            for a in data
        ]}
    return {"ok": True, "data": []}

def update_address(token, address_id, data):
    """Update an existing saved address."""
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Not logged in."}
    return _post(f"{API_BASE}/Api/UpdateAddress", {
        "CustomerID":   token,
        "AddressID":    int(address_id),
        "FriendlyName": data.get("friendly_name", "Home"),
        "Address1":     data.get("address1", ""),
        "Address2":     data.get("address2", ""),
        "Landmark":     data.get("landmark", ""),
        "PostalCode":   data.get("postal_code", ""),
        "AreaID":       data.get("area_id", "1"),
        "Latitude":     "0",
        "Longitude":    "0",
        "City":         data.get("city", ""),
        "State":        data.get("state", ""),
        "Country":      "India",
        "AddressType":  data.get("address_type", "Home"),
    })

def remove_address(token, address_id):
    """Delete a saved address by AddressID."""
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Not logged in."}
    return _post(f"{API_BASE}/Api/RemoveAddress", {
        "CustomerID": token,
        "AddressID":  int(address_id),
    })

def get_areas():
    """
    Fetch list of delivery areas for address form dropdown.
    ⚠ BACKEND NOTE: Confirm exact field names AreaId vs AreaID.
    """
    result = _post(f"{API_BASE}/Api/GetArea", {})
    if not result["ok"]:
        return {"ok": True, "data": []}
    data = result["data"]
    if isinstance(data, list):
        return {"ok": True, "data": [
            {
                "id":   str(a.get("AreaId", a.get("AreaID", a.get("areaId", "")))),
                "name": a.get("AreaName", a.get("Name", ""))
            }
            for a in data if a.get("AreaName") or a.get("Name")
        ]}
    return {"ok": True, "data": []}

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
        "CustomerID":     token,
        "CustomerName":   data.get("name", ""),
        "Email":          data.get("email", ""),
        "CustomerMobile": data.get("phone", ""),
    })
    if not result["ok"]:
        return result

    return {"ok": True, "data": {"user": data}}

def get_shop_status():
    """Check if shop is currently open or closed."""
    try:
        result = _post(f"{API_BASE}/Api/GetShopClosedStatus", {})
        if not result["ok"]:
            return {"is_closed": False, "message": ""}
        data = result["data"]
        # Handle dict response
        if isinstance(data, dict):
            return {
                "is_closed": bool(data.get("IsShopClosed", False)),
                "message":   data.get("ShopClosedMessage", data.get("Message", ""))
            }
        # Handle list response — if list has items, shop might be closed
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            return {
                "is_closed": bool(first.get("IsShopClosed", False)),
                "message":   first.get("ShopClosedMessage", "")
            }
        return {"is_closed": False, "message": ""}
    except Exception:
        return {"is_closed": False, "message": ""}

def get_categories(token=None): # reserved for future personalized results
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

def get_menu_items(token=None, category_id=None, search=None): # reserved for future personalized results
    """Fetch menu items from Lazzatt API."""

    if search:
        result = _post(f"{API_BASE}/Api/GetSearchProduct", {
            "SearchName": search,
            "CustomerId": 0
        })
        if result["ok"]:
            return {"ok": True, "data": [_map_product(p) for p in result["data"]]}
        return {"ok": False, "error": result.get("error", "Search failed.")}

    # Build payload - if category selected, use GetPagerProduct for that type
    if category_id:
        # All category pills from GetProductType use IntrestStatus
        result = _post(f"{API_BASE}/Api/GetProductList", {
            "IntrestStatus": int(category_id),
            "CustomerId":    0
        })
    else:
        result = _post(f"{API_BASE}/Api/GetProduct", {
            "VeganType":  "0",
            "CuisineType": "1"
        })

    if not result["ok"]:
        return {"ok": False, "error": result.get("error", "Could not load menu.")}

    items = [_map_product(p) for p in result["data"]]
    if not category_id:
        cache.set("wtf_all_products", result["data"], timeout=300)
    return {"ok": True, "data": items}

def get_menu_item_detail(item_id, token=None): # reserved for future personalized results
    """
    Fetch a single product by ID.
    Uses cached product list if available - avoids a full API call on every detail page visit.
    Falls back to a fresh API call if cache is empty.
    """
    # Try cache first
    cached_products = cache.get("wtf_all_products")

    if cached_products:
        for raw_item in cached_products:
            if str(raw_item.get("ProductId")) == str(item_id):
                return {"ok": True, "data": _map_product(raw_item)}

    # Cache miss - fetch fresh from API
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

def get_all_banners():
    result = _post(f"{API_BASE}/Api/GetAllBanner", {})
    if not result["ok"]:
        return {"ok": True, "data": []}
    data = result["data"]
    if isinstance(data, list):
        return {"ok": True, "data": [_map_banner(b) for b in data]}
    return {"ok": True, "data": []}

def get_all_offers():
    result = _post(f"{API_BASE}/Api/GetAllOffer", {})
    if not result["ok"]:
        return {"ok": True, "data": []}
    data = result["data"]
    if isinstance(data, list):
        return {"ok": True, "data": [_map_offer(o) for o in data]}
    return {"ok": True, "data": []}

def get_offer_detail(offer_id):
    result = _post(f"{API_BASE}/Api/OfferDetail", {
        "offerID": int(offer_id)
    })
    if not result["ok"]:
        return result
    data = result["data"]
    if isinstance(data, dict):
        return {"ok": True, "data": _map_offer(data)}
    if isinstance(data, list) and data:
        return {"ok": True, "data": _map_offer(data[0])}
    return {"ok": False, "error": "Offer not found."}

def get_loyalty_program():
    result = _post(f"{API_BASE}/Api/GetLoyaltyProgram", {})
    if not result["ok"]:
        return {"ok": True, "data": {}}
    data = result["data"]
    if isinstance(data, dict):
        return {"ok": True, "data": _map_loyalty_program(data)}
    if isinstance(data, list) and data:
        return {"ok": True, "data": _map_loyalty_program(data[0])}
    return {"ok": True, "data": {}}

def get_loyalty_points(token):
    if not token or token.startswith("guest-"):
        return {"ok": True, "data": {"balance": 0}}
    result = _post(f"{API_BASE}/Api/GetLoyaltyPoint", {
        "CustomerID": int(token)
    })
    if not result["ok"]:
        return {"ok": True, "data": {"balance": 0}}
    data = result["data"]
    if isinstance(data, dict):
        return {"ok": True, "data": {
            "balance": data.get("LoyaltyPoint", data.get("Points", 0))
        }}
    if isinstance(data, list) and data:
        return {"ok": True, "data": {
            "balance": data[0].get("LoyaltyPoint", 0)
        }}
    return {"ok": True, "data": {"balance": 0}}

def get_redeem_balance(token):
    if not token or token.startswith("guest-"):
        return {"ok": True, "data": {"balance": 0, "max_redeemable": 0}}
    result = _post(f"{API_BASE}/Api/BalanceRedeemPoint", {
        "CustomerId": int(token)
    })
    if not result["ok"]:
        return {"ok": True, "data": {"balance": 0, "max_redeemable": 0}}
    data = result["data"]
    if isinstance(data, dict):
        return {"ok": True, "data": _map_redeem_balance(data)}
    return {"ok": True, "data": {"balance": 0, "max_redeemable": 0}}

def submit_order_rating(token, order_id, rating, review=""):
    """
    Submit star rating + review for a completed order.
    ⚠ BACKEND NOTE: DetailRating array needs ProductId for each item.
    Currently sending empty array — confirm if this is required.
    """
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Not logged in."}
    return _post(f"{API_BASE}/Api/OrderRating", {
        "OrderId":      int(order_id),
        "OrderRating":  str(rating),
        "WrongStatus":  "no",
        "OrderReview":  review,
        "DetailRating": [],
    })

def get_company_info():
    """
    Fetch restaurant company info for footer/about page.
    ⚠ BACKEND NOTE: Postman body has SaleBillID and Remark — these look
    like test data. Try sending empty body {} first.
    """
    result = _post(f"{API_BASE}/Api/GetCompany", {})
    if not result["ok"]:
        return {"ok": True, "data": {}}
    data = result["data"]
    if isinstance(data, dict):
        return {"ok": True, "data": {
            "name":    data.get("CompanyName", data.get("Name", "")),
            "phone":   data.get("Phone",       data.get("ContactNumber", data.get("Mobile", ""))),
            "email":   data.get("Email",       ""),
            "address": data.get("Address",     data.get("CompanyAddress", "")),
            "about":   data.get("AboutUs",     data.get("About", data.get("Description", ""))),
            "gst":     data.get("GSTNumber",   data.get("GST", "")),
        }}
    return {"ok": True, "data": {}}

def get_cms_pages(token=None):
    """
    Fetch CMS content pages like About Us, Terms & Conditions, Privacy Policy.
    ⚠ BACKEND NOTE: CustomerId is sent in Postman — unclear if it's required.
    Using "0" for guests.
    """
    customer_id = token if (token and not token.startswith("guest-")) else "0"
    result = _post(f"{API_BASE}/Api/GetAllPages", {
        "CustomerId": customer_id
    })
    if not result["ok"]:
        return {"ok": True, "data": []}
    data = result["data"]
    if isinstance(data, list):
        return {"ok": True, "data": [
            {
                "id":      str(p.get("PageID", p.get("PageId", p.get("Id", "")))),
                "title":   p.get("PageTitle",   p.get("Title",   p.get("Name", ""))),
                "content": p.get("PageContent", p.get("Content", p.get("Description", ""))),
                "slug":    p.get("PageSlug",    p.get("Slug",    "")),
            }
            for p in data
        ]}
    return {"ok": True, "data": []}

# ---- Password ----

def change_password(token, old_password, new_password):
    """
    Change password for logged-in user.
    ⚠ BACKEND NOTE: Postman doesn't include CustomerID in body —
    we're adding it assuming it's required. Confirm with backend team.
    """
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Not logged in."}
    return _post(f"{API_BASE}/Api/ChangePassword", {
        "CustomerID":  token,
        "OldPassword": old_password,
        "NewPassword": new_password,
    })

def forgot_password(phone, new_password):
    """
    Reset password via mobile number.
    ⚠ BACKEND NOTE: Unclear if this sends OTP first or resets directly.
    Based on Postman body, appears to reset directly.
    Confirm with backend team if OTP step exists.
    """
    return _post(f"{API_BASE}/Api/ForgotPassword", {
        "CustomerMobile": phone,
        "Password":       new_password,
    })

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
    if not token or token.startswith("guest-"):
        return {"ok": True, "data": {"items": [], "subtotal": 0, "tax": 0, "total": 0}}

    # Use _post_full so we get the complete response including Success field
    headers = {"Content-Type": "application/json"}
    try:
        import requests as req
        resp = req.post(f"{API_BASE}/Api/GetCartList",
                        json={"CustomerID": token, "IsRedeemPoint": False},
                        headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code in (200, 201):
            data = resp.json()
            # Empty cart returns Success:false with "No Data Found"
            # Treat this as a valid empty cart, not an error
            if not data.get("Success"):
                msg = data.get("Message", "")
                if "no data" in msg.lower() or "not found" in msg.lower() or data.get("CartCount", -1) == 0:
                    return {"ok": True, "data": {"items": [], "subtotal": 0, "tax": 0, "total": 0}}
                return {"ok": False, "error": msg}
            return {"ok": True, "data": _build_cart_from_api(data)}
    except Exception:
        pass

    return {"ok": True, "data": {"items": [], "subtotal": 0, "tax": 0, "total": 0}}

def add_to_cart(token, item_id, quantity, special_instructions=""): # Lazzatt API doesn't support special instructions — kept for interface consistency
    """Add item to cart. Requires logged-in user (CustomerID)."""
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Please log in to add items to cart."}

    # First, the item price - fetch it from the product list
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
    """Clear cart by removing all items one by one - Lazzatt has no bulk clear endpoint."""
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

def place_order(token, delivery_address, special_note="", redeem_points=False):
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Please log in to place an order."}

    # Step 1 - Save address and get AddressID
    address_result = _post(f"{API_BASE}/Api/AddAddress", {
        "CustomerID":   token,
        "FriendlyName": "Delivery Address",
        "Address1":     delivery_address,
        "Address2":     "",
        "Landmark":     "",
        "PostalCode":   "",
        "AreaID":       "1",       # Default area - update once GetArea is integrated
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

    # Step 2 - Place order
    result = _post(f"{API_BASE}/Api/OrderPlaced", {
        "CustomerId":           int(token),
        "AddressID":            address_id,
        "PaymentMethod":        1,          # 1 = Cash on Delivery, 2 = Online payment
        "OrderType":            1,          # 1 = Delivery
        "IsRedeemPoint":        redeem_points,
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
    order_id = raw.get("CustomerOrderID") or raw.get("OrderId") or "0"

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

def reorder(token):
    """
    Re-add last order items to cart.
    ⚠ BACKEND NOTE: Postman only shows CustomerID in body.
    Unclear if this re-orders the LAST order or a specific one.
    Confirm with backend whether an OrderID/SaleBillID is needed.
    """
    if not token or token.startswith("guest-"):
        return {"ok": False, "error": "Please log in."}
    return _post(f"{API_BASE}/Api/Reorder", {
        "CustomerID": token
    })

def get_live_orders(token):
    if not token or token.startswith("guest-"):
        return {"ok": True, "data": []}
    result = _post(f"{API_BASE}/Api/GetLiveOrders", {
        "CustomerID": int(token)
    })
    if not result["ok"]:
        return {"ok": True, "data": []}
    data = result["data"]
    if isinstance(data, list):
        return {"ok": True, "data": [_map_live_order(o) for o in data]}
    if isinstance(data, dict):
        return {"ok": True, "data": [_map_live_order(data)]}
    return {"ok": True, "data": []}

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
    """Lazzatt handles payment externally - no status endpoint available."""
    return {"ok": True, "data": {"status": "success"}}