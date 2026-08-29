from django.contrib import admin
from .models import (
    Supplier, Purchase, PurchaseItem,
    Sale, SaleItem, Expense, AccountsReceivable, CardReconciliation
)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'cnpj_cpf', 'phone', 'email', 'created_at')
    search_fields = ('name', 'cnpj_cpf', 'email')

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'invoice_number', 'date', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'supplier')
    inlines = [PurchaseItemInline]

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sale_code', 'customer_name', 'sale_type', 'payment_method', 'gross_amount', 'discount', 'net_amount', 'status', 'date')
    list_filter = ('sale_type', 'payment_method', 'status')
    search_fields = ('sale_code', 'customer_name')
    inlines = [SaleItemInline]

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'category', 'amount', 'due_date', 'status', 'is_paid')
    list_filter = ('status', 'category')
    search_fields = ('description', 'category')

@admin.register(AccountsReceivable)
class AccountsReceivableAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'description', 'total_amount', 'due_date', 'status', 'payment_method')
    list_filter = ('status', 'payment_method')
    search_fields = ('customer_name', 'description')

@admin.register(CardReconciliation)
class CardReconciliationAdmin(admin.ModelAdmin):
    list_display = ('sale', 'card_brand', 'transaction_type', 'gross_amount', 'fee_percentage', 'fee_amount', 'net_amount', 'status')
    list_filter = ('status', 'card_brand', 'transaction_type')
