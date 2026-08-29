from django.contrib import admin
from .models import Supplier, Product

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_name', 'phone')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('cod_unico', 'descricao', 'cor', 'tamanho', 'preco_custo', 'preco_venda', 'quantidade', 'fornecedor')
    search_fields = ('cod_unico', 'descricao', 'cor')
    list_filter = ('categoria', 'fornecedor')
