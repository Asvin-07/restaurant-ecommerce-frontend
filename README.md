# Way To Food (WTF) - Restaurant Ordering App
## B.Tech Project - Asvin Nigam | 202252343

This is my frontend for a customer-facing restaurant e-commerce web application,
built as part of my B.Tech project at IIIT Vadodara.

The app lets customers browse the menu, add items to cart, and place orders.
It is built using Django and plain HTML/CSS/JS - no frontend framework.

Connected to the Lazzatt backend API. All menu, cart, and order data is live.
---

## How to Run

1. Make sure Python is installed
2. Install dependencies:
   pip install -r requirements.txt
3. Run migrations (needed for sessions):
   python manage.py migrate
4. Start the server:
   python manage.py runserver
5. Open http://127.0.0.1:8000 in your browser

---

## Pages

| URL | What it does |
|-----|-------------|
| `/` | Menu page - browse all food items |
| `/login/` | Login with mobile + password |
| `/register/` | Create a new account |
| `/cart/` | View and edit your cart |
| `/checkout/` | Enter address and place order |
| `/orders/` | View past orders |
| `/orders/<id>/` | Order detail page |
| `/profile/` | Edit your profile |

---

## Project Structure
```
customer_app/
    api_service.py   ← all API calls go here (Lazzatt API integration)
    views.py         ← handles requests and passes data to templates
    urls.py          ← URL routing
templates/
    base.html        ← navbar, footer, shared layout
    menu.html        ← menu grid with category filter
    cart.html        ← cart page
    checkout.html    ← checkout page
    ...
static/
    css/styles.css   ← all custom styles
    js/main.js       ← cart AJAX logic
```

---

## Tech Stack

- Python 3 + Django 5
- Plain CSS (no Bootstrap or Tailwind)
- Vanilla JavaScript (no React or Vue)
- SQLite (for Django sessions only)