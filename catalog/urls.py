from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.visual_catalog, name='visual_catalog'),
    path('quick-view/<str:code_or_id>/', views.quick_view_modal, name='quick_view_modal'),
    path('scanner/', views.scanner_view, name='scanner'),
    path('scan-lookup/', views.scan_lookup_view, name='scan_lookup_query'),
    path('scan-lookup/<str:code_unico>/', views.scan_lookup_view, name='scan_lookup'),
    path('labels/', views.label_generator_view, name='label_generator'),
    path('labels/preview/', views.label_preview_view, name='label_preview'),
    path('labels/print/', views.label_print_view, name='label_print'),
]
