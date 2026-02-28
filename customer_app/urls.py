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
]
