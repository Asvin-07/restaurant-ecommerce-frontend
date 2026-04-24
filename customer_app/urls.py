from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.menu_view, name='menu'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Menu
    path('menu/', views.menu_view, name='menu'),
    path('menu/<str:item_id>/', views.item_detail_view, name='item_detail'),
    path('api/menu-items/', views.menu_items_json, name='menu_items_json'),

    # Cart (page)
    path('cart/', views.cart_view, name='cart'),

    # Cart AJAX endpoints
    path('cart/add/', views.add_to_cart_view, name='cart_add'),
    path('cart/decrement/', views.decrement_cart_item_by_item_id_view, name='cart_decrement'),
    path('cart/items/<str:cart_item_id>/update/', views.update_cart_item_view, name='cart_update'),
    path('cart/items/<str:cart_item_id>/remove/', views.remove_cart_item_view, name='cart_remove'),
    path('cart/clear/', views.clear_cart_view, name='cart_clear'),

    # Checkout & Payment
    path('checkout/', views.checkout_view, name='checkout'),
    path('payment/return/', views.payment_return_view, name='payment_return'),

    # Orders
    path('orders/', views.order_history_view, name='order_history'),
    path('orders/<str:order_id>/', views.order_detail_view, name='order_detail'),
    path('orders/<str:order_id>/confirmation/', views.order_confirmation_view, name='order_confirmation'),

    # Profile
    path('profile/', views.profile_view, name='profile'),
    
    # Auth extras
    path('change-password/', views.change_password_view, name='change_password'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),

    # Addresses
    path('addresses/', views.addresses_view, name='addresses'),

    # Orders extended
    path('orders/<str:order_id>/reorder/', views.reorder_view, name='reorder'),
    path('orders/<str:order_id>/rate/', views.submit_rating_view, name='submit_rating'),

    # Live orders
    path('live-orders/', views.live_orders_view, name='live_orders'),

    # Offers
    path('offers/', views.offers_view, name='offers'),
    path('offers/<str:offer_id>/', views.offer_detail_view, name='offer_detail'),

    # Loyalty
    path('loyalty/', views.loyalty_view, name='loyalty'),

    # Content pages
    path('about/', views.company_view, name='about'),
    path('pages/', views.cms_page_view, name='cms_pages'),
    path('pages/<str:page_id>/', views.cms_page_view, name='cms_page'),
]