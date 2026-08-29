from django.contrib import admin
from .models import ProductImage, BarcodeLabelTemplate

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'is_primary', 'created_at')

@admin.register(BarcodeLabelTemplate)
class BarcodeLabelTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'printer_type', 'width_mm', 'height_mm')
