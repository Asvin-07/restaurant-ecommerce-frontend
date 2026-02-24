# Way To Food (WTF) — Customer Restaurant E-Commerce App

A production-quality Django frontend that consumes your existing restaurant backend APIs.
No business logic is implemented here — all data flows through `api_service.py`.

---

## 🚀 Quick Start

```bash
# 1. Navigate to project directory
cd Restaurant_BTP

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your backend API URL
export API_BASE_URL=http://your-backend.com/api   # Windows: set API_BASE_URL=...

# 5. Run migrations (for sessions)
python manage.py migrate

# 6. Start the development server
python manage.py runserver
```

Visit: http://127.0.0.1:8000

---

## 📁 Project Structure

```
Restaurant_BTP/
├── customer_app/
│   ├── api_service.py     ← ALL API calls (centralized)
│   ├── views.py           ← Django views (orchestrate API + render templates)
│   └── urls.py            ← URL routing
├── templates/
│   ├── base.html          ← Navbar, footer, messages
│   ├── login.html
│   ├── register.html
│   ├── menu.html          ← Menu browsing with category filter + search
│   ├── item_detail.html   ← Single item detail + add to cart
│   ├── cart.html          ← Cart page with AJAX qty updates
│   ├── checkout.html      ← Address input + order summary
│   ├── order_confirmation.html
│   ├── payment_return.html ← Handles payment gateway redirect back
│   ├── order_history.html
│   ├── order_detail.html
│   └── profile.html
├── static/
│   ├── css/styles.css        ← All custom styles
│   └── js/main.js          ← AJAX cart logic, toasts, interactions
└── restaurant_core/
    └── settings.py        ← API_BASE_URL, session config, static files
```

---

## 🔌 API Integration

All API calls go through `customer_app/api_service.py`. Configure your backend URL:

```python
# In settings.py or via environment variable:
API_BASE_URL = "http://your-backend.com/api"
```

### Expected API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login/` | Login with phone + password |
| POST | `/auth/register/` | Create account |
| GET | `/auth/profile/` | Get user profile |
| PUT | `/auth/profile/` | Update profile |
| GET | `/menu/categories/` | All categories |
| GET | `/menu/items/` | Menu items (supports `?category=&search=`) |
| GET | `/menu/items/{id}/` | Item detail |
| GET | `/cart/` | Get current cart |
| POST | `/cart/add/` | Add item to cart |
| PUT | `/cart/items/{id}/` | Update cart item quantity |
| DELETE | `/cart/items/{id}/` | Remove cart item |
| POST | `/orders/` | Place order |
| GET | `/orders/` | Order history |
| GET | `/orders/{id}/` | Order detail |
| POST | `/payments/initiate/` | Initiate payment (returns `payment_url`) |
| GET | `/payments/{id}/status/` | Payment status |

### Auth Token

The backend should return a `token` field in login/register responses:
```json
{ "token": "eyJ...", "user": { "id": 1, "name": "...", "phone": "..." } }
```
Tokens are stored in Django sessions (server-side, secure).

---

## 🔒 Security Notes

- Auth tokens are stored in Django's server-side session (not localStorage)
- CSRF protection is active on all POST forms and AJAX calls
- API errors are sanitized before display (no internal details leaked)
- Set `SESSION_COOKIE_SECURE=True` and `DEBUG=False` in production

---

## 🎨 Design

- **Font**: Playfair Display (headings) + Nunito (body)
- **Colors**: Crimson red `#C0392B` + Saffron gold `#E67E22` on cream `#fdf6ee`
- **Mobile-first**: Fully responsive grid-based layout
- All styles in `static/css/styles.css` — no framework dependency beyond Google Fonts

---

## 🔮 Future Improvements

- PWA support with service worker for offline menu browsing
- Real-time order tracking via WebSockets
- Saved addresses management
- Loyalty points display
- Personalized recommendations
- Multi-language support (i18n)
- Dark mode toggle
