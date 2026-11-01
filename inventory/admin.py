from django.contrib import admin
from .models import Supplier, Product, Category
from catalog.models import ProductImage

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'is_primary', 'alt_text')

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_name', 'phone')
    search_fields = ('name', 'contact_name')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('cod_unico', 'descricao', 'cor', 'tamanho', 'preco_venda', 'quantidade', 'exibir_no_site', 'destaque_vitrine', 'categoria')
    list_editable = ('preco_venda', 'quantidade', 'exibir_no_site', 'destaque_vitrine')
    search_fields = ('cod_unico', 'descricao', 'cor', 'tamanho')
    list_filter = ('exibir_no_site', 'destaque_vitrine', 'categoria', 'fornecedor', 'tamanho')
    list_per_page = 25
    inlines = [ProductImageInline]
