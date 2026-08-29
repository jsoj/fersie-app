from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('bulk-action/', views.product_bulk_action, name='product_bulk_action'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
]


