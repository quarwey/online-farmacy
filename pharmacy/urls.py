from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("catalog/", views.catalog, name="catalog"),
    path("catalog/medicine/<int:pk>/", views.medicine_detail, name="medicine_detail"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:pk>/", views.add_to_cart, name="add_to_cart"),
    path("order/create/", views.checkout, name="checkout"),
    path("profile/", views.profile, name="profile"),
    path("profile/orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("profile/orders/<int:order_id>/recipe/", views.recipe_upload, name="recipe_upload"),
    path("pharmacist/recipes/", views.pharmacist_recipes, name="pharmacist_recipes"),
    path("pharmacist/recipes/<int:pk>/", views.recipe_review, name="recipe_review"),
]

