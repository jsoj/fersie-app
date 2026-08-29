from django.urls import path
from . import views

app_name = 'financial'

urlpatterns = [
    # Dashboard Overview
    path('', views.financial_overview, name='overview'),

    # Sales Checkout & History
    path('sales/', views.sales_list, name='sales_list'),
    path('sales/bulk-action/', views.sales_bulk_action, name='sales_bulk_action'),
    path('sales/create/', views.sales_create, name='sales_create'),
    path('sales/add-item-row/', views.sales_add_item_row, name='sales_add_item_row'),

    # Purchases & Supplier Management
    path('purchases/', views.purchases_list, name='purchases_list'),
    path('purchases/bulk-action/', views.purchases_bulk_action, name='purchases_bulk_action'),
    path('purchases/create/', views.purchases_create, name='purchases_create'),

    # Operational Expenses
    path('expenses/', views.expenses_list, name='expenses_list'),
    path('expenses/bulk-action/', views.expenses_bulk_action, name='expenses_bulk_action'),
    path('expenses/<int:pk>/mark-paid/', views.expense_mark_paid, name='expense_mark_paid'),

    # Accounts Receivable Tracker
    path('receivables/', views.receivables_list, name='receivables_list'),
    path('receivables/bulk-action/', views.receivables_bulk_action, name='receivables_bulk_action'),
    path('receivables/<int:pk>/mark-paid/', views.receivable_mark_paid, name='receivable_mark_paid'),

    # Card Fee Reconciliation
    path('reconciliation/', views.reconciliation_list, name='reconciliation_list'),
    path('reconciliation/bulk-action/', views.reconciliation_bulk_action, name='reconciliation_bulk_action'),
    path('reconciliation/<int:pk>/toggle-status/', views.reconciliation_toggle_status, name='reconciliation_toggle_status'),

]
