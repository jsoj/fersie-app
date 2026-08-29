from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Q
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib import messages
from inventory.models import Product, Supplier as InventorySupplier
from .models import (
    Supplier, Purchase, PurchaseItem,
    Sale, SaleItem, Expense, AccountsReceivable, CardReconciliation
)
from .services import process_sale_checkout, process_purchase_ingestion


def financial_overview(request):
    """
    Dashboard view (/financial/):
    Summary cards (Total Sales, Total Expenses, Net Profit, Pending Receivables, Card Fees total)
    and HTMX dynamic tables with totalizer rows (.fersie-totalizer-row).
    """
    sales = Sale.objects.filter(status='completed')
    expenses = Expense.objects.all()
    receivables = AccountsReceivable.objects.all()
    reconciliations = CardReconciliation.objects.all()

    total_sales = sales.aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    net_profit = total_sales - total_expenses
    pending_receivables = receivables.filter(status='pendente').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    card_fees_total = reconciliations.aggregate(total=Sum('fee_amount'))['total'] or Decimal('0.00')

    # Recent items for dashboard summary tables
    recent_sales = sales.order_by('-created_at')[:5]
    recent_expenses = expenses.order_by('-due_date')[:5]
    pending_card_rec = reconciliations.order_by('-created_at')[:5]

    context = {
        'total_sales': round(total_sales, 2),
        'total_expenses': round(total_expenses, 2),
        'net_profit': round(net_profit, 2),
        'pending_receivables': round(pending_receivables, 2),
        'card_fees_total': round(card_fees_total, 2),
        'sales': sales,
        'recent_sales': recent_sales,
        'recent_expenses': recent_expenses,
        'pending_card_rec': pending_card_rec,
        'expenses': expenses,
        'receivables': receivables,
        'reconciliations': reconciliations,
    }

    if request.headers.get('HX-Request') and request.GET.get('table_only'):
        return render(request, 'financial/partials/overview_tables.html', context)

    return render(request, 'financial/overview.html', context)


# Allowed Sort Maps
ALLOWED_SALES_SORT = {'sale_code', 'date', 'created_at', 'customer_name', 'gross_amount', 'discount', 'net_amount', 'status', 'payment_method'}
ALLOWED_PURCHASES_SORT = {'id', 'date', 'created_at', 'supplier__name', 'invoice_number', 'total_amount', 'status'}
ALLOWED_EXPENSES_SORT = {'description', 'category', 'due_date', 'payment_date', 'amount', 'status'}
ALLOWED_RECEIVABLES_SORT = {'customer_name', 'description', 'due_date', 'received_date', 'total_amount', 'received_amount', 'status'}
ALLOWED_RECONCILIATION_SORT = {'sale__sale_code', 'card_brand', 'transaction_type', 'gross_amount', 'fee_percentage', 'fee_amount', 'net_amount', 'expected_settlement_date', 'status'}


def sales_list(request):
    """
    Sales list view (/financial/sales/):
    Lists all sales with search, filter, multi-column sorting, pagination, dynamic totalizers and bulk actions.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    pm_filter = request.GET.get('payment_method', '').strip()
    sale_type_filter = request.GET.get('sale_type', '').strip()
    sort_param = request.GET.get('sort', '').strip()
    page_number = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 10))

    sales = Sale.objects.all()

    if query:
        sales = sales.filter(Q(sale_code__icontains=query) | Q(customer_name__icontains=query))
    if status_filter:
        sales = sales.filter(status=status_filter)
    if pm_filter:
        sales = sales.filter(payment_method=pm_filter)
    if sale_type_filter:
        sales = sales.filter(sale_type=sale_type_filter)

    # Sorting
    if sort_param:
        clean_field = sort_param.lstrip('-')
        if clean_field in ALLOWED_SALES_SORT:
            sales = sales.order_by(sort_param)
        else:
            sales = sales.order_by('-created_at')
    else:
        sales = sales.order_by('-created_at')

    # Aggregates across filtered sales QS
    total_count = sales.count()
    total_gross = sales.aggregate(total=Sum('gross_amount'))['total'] or Decimal('0.00')
    total_discount = sales.aggregate(total=Sum('discount'))['total'] or Decimal('0.00')
    total_revenue = sales.aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')

    # Total items sold calculation
    items_qty = SaleItem.objects.filter(sale__in=sales).aggregate(total=Sum('quantity'))['total'] or 0
    legacy_qty = sales.filter(items__isnull=True).aggregate(total=Sum('quantity'))['total'] or 0
    total_items_sold = items_qty + legacy_qty

    # Cost of goods sold & Margin calculation
    cost_items = sum(
        (item.product.preco_custo or Decimal('0.00')) * item.quantity
        for item in SaleItem.objects.filter(sale__in=sales).select_related('product')
    )
    cost_legacy = sum(
        ((s.product.preco_custo if s.product else Decimal('0.00')) or Decimal('0.00')) * (s.quantity or 1)
        for s in sales.filter(items__isnull=True).select_related('product')
    )
    total_cogs = cost_items + cost_legacy
    total_margin = total_revenue - total_cogs

    # Pagination
    paginator = Paginator(sales, per_page)
    page_obj = paginator.get_page(page_number)

    context = {
        'sales': page_obj,
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'pm_filter': pm_filter,
        'sale_type_filter': sale_type_filter,
        'current_sort': sort_param,
        'total_count': total_count,
        'total_items_sold': total_items_sold,
        'total_gross': round(total_gross, 2),
        'total_discount': round(total_discount, 2),
        'total_revenue': round(total_revenue, 2),
        'total_net': round(total_revenue, 2),
        'total_margin': round(total_margin, 2),
        'per_page': per_page,
    }

    if request.headers.get('HX-Request') or request.GET.get('table_only'):
        return render(request, 'financial/partials/sales_table.html', context)

    return render(request, 'financial/sales_list.html', context)


def sales_bulk_action(request):
    """
    HTMX Endpoint for bulk operations on sales (mark completed, mark cancelled, delete).
    """
    if request.method == 'POST':
        action = request.POST.get('bulk_action', '').strip()
        selected_ids = request.POST.getlist('selected_ids')

        if selected_ids and action:
            selected_sales = Sale.objects.filter(id__in=selected_ids)
            if action == 'completed':
                selected_sales.update(status='completed')
                messages.success(request, f"{selected_sales.count()} vendas marcadas como concluídas.")
            elif action == 'cancelled':
                selected_sales.update(status='cancelled')
                messages.success(request, f"{selected_sales.count()} vendas marcadas como canceladas.")
            elif action == 'delete':
                count = selected_sales.count()
                selected_sales.delete()
                messages.success(request, f"{count} vendas excluídas.")

    return sales_list(request)


def sales_create(request):
    """
    Sales Checkout View (/financial/sales/create/):
    Checkout interface with HTMX dynamic item addition and stock validation.
    """
    products = Product.objects.filter(quantidade__gt=0).order_by('descricao')
    error_message = None

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        sale_type = request.POST.get('sale_type', 'balcao')
        payment_method = request.POST.get('payment_method', 'dinheiro')
        discount_str = request.POST.get('discount', '0.00')
        card_brand = request.POST.get('card_brand', 'visa')
        transaction_type = request.POST.get('transaction_type', '')
        installment_count_str = request.POST.get('installment_count', '1')

        try:
            discount = Decimal(str(discount_str or 0))
        except Exception:
            discount = Decimal('0.00')

        try:
            installment_count = int(installment_count_str or 1)
        except Exception:
            installment_count = 1

        product_ids = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        unit_prices = request.POST.getlist('unit_price')

        items = []
        for i in range(len(product_ids)):
            p_id = product_ids[i]
            if not p_id:
                continue
            qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 1
            
            if i < len(unit_prices) and unit_prices[i]:
                u_price = Decimal(str(unit_prices[i]))
            else:
                prod = Product.objects.get(id=p_id)
                u_price = prod.preco_venda

            items.append({
                'product_id': p_id,
                'quantity': qty,
                'unit_price': u_price
            })

        try:
            sale = process_sale_checkout(
                customer_name=customer_name,
                sale_type=sale_type,
                payment_method=payment_method,
                discount=discount,
                items=items,
                card_brand=card_brand,
                transaction_type=transaction_type,
                installment_count=installment_count
            )
            return redirect('financial:sales_list')
        except ValueError as e:
            error_message = str(e)
            if request.headers.get('HX-Request'):
                return render(request, 'financial/partials/sale_error.html', {'error_message': error_message}, status=400)

    context = {
        'products': products,
        'error_message': error_message,
    }
    return render(request, 'financial/sales_create.html', context)


def sales_add_item_row(request):
    """
    HTMX endpoint for adding a product row to the sales checkout form.
    """
    products = Product.objects.filter(quantidade__gt=0).order_by('descricao')
    row_index = request.GET.get('row_index', '0')
    return render(request, 'financial/partials/sale_item_row.html', {
        'products': products,
        'row_index': row_index,
    })


def purchases_list(request):
    """
    Purchases list view (/financial/purchases/):
    Lists purchases with supplier info, date, multi-column sorting, pagination, dynamic totalizers and bulk actions.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    supplier_filter = request.GET.get('supplier', '').strip()
    sort_param = request.GET.get('sort', '').strip()
    page_number = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 10))

    purchases = Purchase.objects.all()

    if query:
        purchases = purchases.filter(Q(supplier__name__icontains=query) | Q(invoice_number__icontains=query) | Q(notes__icontains=query))
    if status_filter:
        purchases = purchases.filter(status=status_filter)
    if supplier_filter:
        purchases = purchases.filter(supplier_id=supplier_filter)

    # Sorting
    if sort_param:
        clean_field = sort_param.lstrip('-')
        if clean_field in ALLOWED_PURCHASES_SORT:
            purchases = purchases.order_by(sort_param)
        else:
            purchases = purchases.order_by('-date', '-created_at')
    else:
        purchases = purchases.order_by('-date', '-created_at')

    # Dynamic Aggregates across filtered purchases QS
    total_count = purchases.count()
    total_amount = purchases.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_purchase_cost = total_amount
    total_quantity_purchased = PurchaseItem.objects.filter(purchase__in=purchases).aggregate(total=Sum('quantity'))['total'] or 0

    # Pagination
    paginator = Paginator(purchases, per_page)
    page_obj = paginator.get_page(page_number)
    suppliers = Supplier.objects.all().order_by('name')

    context = {
        'purchases': page_obj,
        'page_obj': page_obj,
        'suppliers': suppliers,
        'query': query,
        'status_filter': status_filter,
        'supplier_filter': supplier_filter,
        'current_sort': sort_param,
        'total_amount': round(total_amount, 2),
        'total_purchase_cost': round(total_purchase_cost, 2),
        'total_quantity_purchased': total_quantity_purchased,
        'total_count': total_count,
        'per_page': per_page,
    }

    if request.headers.get('HX-Request') or request.GET.get('table_only'):
        return render(request, 'financial/partials/purchases_table.html', context)

    return render(request, 'financial/purchases_list.html', context)


def purchases_bulk_action(request):
    """
    HTMX Endpoint for bulk operations on purchases (mark paid, mark pending, delete).
    """
    if request.method == 'POST':
        action = request.POST.get('bulk_action', '').strip()
        selected_ids = request.POST.getlist('selected_ids')

        if selected_ids and action:
            selected_purchases = Purchase.objects.filter(id__in=selected_ids)
            if action == 'mark_paid':
                selected_purchases.update(status='paid')
                messages.success(request, f"{selected_purchases.count()} compras marcadas como pagas.")
            elif action == 'mark_pending':
                selected_purchases.update(status='pending')
                messages.success(request, f"{selected_purchases.count()} compras marcadas como pendentes.")
            elif action == 'delete':
                count = selected_purchases.count()
                selected_purchases.delete()
                messages.success(request, f"{count} compras excluídas.")

    return purchases_list(request)


def purchases_create(request):
    """
    Purchase Ingestion View (/financial/purchases/create/):
    Form to register purchase orders and increase product stock.
    """
    suppliers = Supplier.objects.all().order_by('name')
    products = Product.objects.all().order_by('descricao')
    error_message = None

    if request.method == 'POST' and 'create_supplier' in request.POST:
        sup_name = request.POST.get('supplier_name', '').strip()
        sup_cnpj = request.POST.get('cnpj_cpf', '').strip()
        sup_phone = request.POST.get('phone', '').strip()
        sup_email = request.POST.get('email', '').strip()
        if sup_name:
            Supplier.objects.get_or_create(
                name=sup_name,
                defaults={'cnpj_cpf': sup_cnpj, 'phone': sup_phone, 'email': sup_email}
            )
            return redirect('financial:purchases_create')

    if request.method == 'POST' and 'create_purchase' in request.POST:
        supplier_id = request.POST.get('supplier_id')
        invoice_number = request.POST.get('invoice_number', '').strip()
        status = request.POST.get('status', 'pending')
        notes = request.POST.get('notes', '').strip()

        product_ids = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        unit_costs = request.POST.getlist('unit_cost')

        items = []
        for i in range(len(product_ids)):
            p_id = product_ids[i]
            if not p_id:
                continue
            qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 1
            if i < len(unit_costs) and unit_costs[i]:
                u_cost = Decimal(str(unit_costs[i]))
            else:
                prod = Product.objects.get(id=p_id)
                u_cost = prod.preco_custo

            items.append({
                'product_id': p_id,
                'quantity': qty,
                'unit_cost': u_cost
            })

        try:
            supplier = Supplier.objects.get(id=supplier_id)
            process_purchase_ingestion(
                supplier=supplier,
                invoice_number=invoice_number,
                status=status,
                notes=notes,
                items=items
            )
            return redirect('financial:purchases_list')
        except Exception as e:
            error_message = str(e)

    context = {
        'suppliers': suppliers,
        'products': products,
        'error_message': error_message,
    }
    return render(request, 'financial/purchases_create.html', context)


def expenses_list(request):
    """
    Expense view (/financial/expenses/):
    Form & list of operational expenses with search, category/status filter, sorting, pagination, totalizers, and bulk actions.
    """
    query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', '').strip()
    sort_param = request.GET.get('sort', '').strip()
    page_number = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 10))

    if request.method == 'POST' and not request.POST.get('bulk_action'):
        description = request.POST.get('description', '').strip()
        category = request.POST.get('category', 'operacional')
        amount_str = request.POST.get('amount', '0.00')
        due_date = request.POST.get('due_date')
        status = request.POST.get('status', 'pendente')
        receipt_notes = request.POST.get('receipt_notes', '').strip()

        if description and amount_str and due_date:
            amount = Decimal(str(amount_str))
            payment_date = timezone.now().date() if status == 'pago' else None
            Expense.objects.create(
                description=description,
                category=category,
                amount=amount,
                due_date=due_date,
                status=status,
                payment_date=payment_date,
                receipt_notes=receipt_notes
            )
            return redirect('financial:expenses_list')

    expenses = Expense.objects.all()

    if query:
        expenses = expenses.filter(Q(description__icontains=query) | Q(receipt_notes__icontains=query))
    if category_filter:
        expenses = expenses.filter(category=category_filter)
    if status_filter:
        expenses = expenses.filter(status=status_filter)

    # Sorting
    if sort_param:
        clean_field = sort_param.lstrip('-')
        if clean_field in ALLOWED_EXPENSES_SORT:
            expenses = expenses.order_by(sort_param)
        else:
            expenses = expenses.order_by('-due_date', '-created_at')
    else:
        expenses = expenses.order_by('-due_date', '-created_at')

    # Aggregates across filtered QS
    total_amount = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_expense_amount = total_amount
    total_count = expenses.count()

    # Pagination
    paginator = Paginator(expenses, per_page)
    page_obj = paginator.get_page(page_number)

    context = {
        'expenses': page_obj,
        'page_obj': page_obj,
        'query': query,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'current_sort': sort_param,
        'total_amount': round(total_amount, 2),
        'total_expense_amount': round(total_expense_amount, 2),
        'total_count': total_count,
        'categories': Expense.CATEGORY_CHOICES,
        'per_page': per_page,
    }

    if request.headers.get('HX-Request') or request.GET.get('table_only'):
        return render(request, 'financial/partials/expenses_table.html', context)

    return render(request, 'financial/expenses_list.html', context)


def expenses_bulk_action(request):
    """
    HTMX Endpoint for bulk operations on expenses (mark paid, mark pending, delete).
    """
    if request.method == 'POST':
        action = request.POST.get('bulk_action', '').strip()
        selected_ids = request.POST.getlist('selected_ids')

        if selected_ids and action:
            selected_expenses = Expense.objects.filter(id__in=selected_ids)
            if action == 'mark_paid':
                today = timezone.now().date()
                selected_expenses.update(status='pago', payment_date=today)
                messages.success(request, f"{selected_expenses.count()} despesas marcadas como pagas.")
            elif action == 'mark_pending':
                selected_expenses.update(status='pendente', payment_date=None)
                messages.success(request, f"{selected_expenses.count()} despesas marcadas como pendentes.")
            elif action == 'delete':
                count = selected_expenses.count()
                selected_expenses.delete()
                messages.success(request, f"{count} despesas excluídas.")

    return expenses_list(request)


def expense_mark_paid(request, pk):
    """
    HTMX action to mark an expense as paid.
    """
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        expense.status = 'pago'
        expense.payment_date = timezone.now().date()
        expense.save()

    if request.headers.get('HX-Request'):
        return render(request, 'financial/partials/expense_row.html', {'expense': expense})
    return redirect('financial:expenses_list')


def receivables_list(request):
    """
    Receivables view (/financial/receivables/):
    Receivables tracker with filtering, sorting, pagination, dynamic totalizer row and bulk actions.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    pm_filter = request.GET.get('payment_method', '').strip()
    sort_param = request.GET.get('sort', '').strip()
    page_number = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 10))

    receivables = AccountsReceivable.objects.all()

    if status_filter:
        receivables = receivables.filter(status=status_filter)
    if query:
        receivables = receivables.filter(Q(customer_name__icontains=query) | Q(description__icontains=query))
    if pm_filter:
        receivables = receivables.filter(payment_method=pm_filter)

    # Sorting
    if sort_param:
        clean_field = sort_param.lstrip('-')
        if clean_field in ALLOWED_RECEIVABLES_SORT:
            receivables = receivables.order_by(sort_param)
        else:
            receivables = receivables.order_by('-due_date', '-created_at')
    else:
        receivables = receivables.order_by('-due_date', '-created_at')

    # Aggregates across filtered QS
    total_count = receivables.count()
    total_amount = receivables.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    pending_amount = receivables.filter(status='pendente').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    # Calculate total_received_amount correctly for paid items
    paid_qs = receivables.filter(status='pago')
    paid_sum_rec = paid_qs.aggregate(total=Sum('received_amount'))['total'] or Decimal('0.00')
    if paid_sum_rec == Decimal('0.00') and paid_qs.exists():
        paid_amount = paid_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    else:
        paid_amount = paid_sum_rec

    total_outstanding_amount = pending_amount
    total_received_amount = paid_amount

    # Pagination
    paginator = Paginator(receivables, per_page)
    page_obj = paginator.get_page(page_number)

    context = {
        'receivables': page_obj,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'pm_filter': pm_filter,
        'query': query,
        'current_sort': sort_param,
        'total_amount': round(total_amount, 2),
        'pending_amount': round(pending_amount, 2),
        'paid_amount': round(paid_amount, 2),
        'total_outstanding_amount': round(total_outstanding_amount, 2),
        'total_received_amount': round(total_received_amount, 2),
        'total_count': total_count,
        'per_page': per_page,
    }

    if request.headers.get('HX-Request') or request.GET.get('table_only'):
        return render(request, 'financial/partials/receivables_table.html', context)

    return render(request, 'financial/receivables_list.html', context)


def receivables_bulk_action(request):
    """
    HTMX Endpoint for bulk operations on receivables (mark paid, mark pending, delete).
    """
    if request.method == 'POST':
        action = request.POST.get('bulk_action', '').strip()
        selected_ids = request.POST.getlist('selected_ids')

        if selected_ids and action:
            selected_recs = AccountsReceivable.objects.filter(id__in=selected_ids)
            if action == 'mark_paid':
                today = timezone.now().date()
                for rec in selected_recs:
                    rec.status = 'pago'
                    rec.received_amount = rec.total_amount
                    rec.received_date = today
                    rec.save()
                messages.success(request, f"{selected_recs.count()} recebíveis marcados como pagos.")
            elif action == 'mark_pending':
                selected_recs.update(status='pendente', received_amount=Decimal('0.00'), received_date=None)
                messages.success(request, f"{selected_recs.count()} recebíveis marcados como pendentes.")
            elif action == 'delete':
                count = selected_recs.count()
                selected_recs.delete()
                messages.success(request, f"{count} recebíveis excluídos.")

    return receivables_list(request)


def receivable_mark_paid(request, pk):
    """
    HTMX action to mark a receivable record as paid.
    """
    rec = get_object_or_404(AccountsReceivable, pk=pk)
    if request.method == 'POST':
        rec.status = 'pago'
        rec.received_amount = rec.total_amount
        rec.received_date = timezone.now().date()
        rec.save()

    if request.headers.get('HX-Request'):
        return render(request, 'financial/partials/receivable_row.html', {'receivable': rec})
    return redirect('financial:receivables_list')


def reconciliation_list(request):
    """
    Card Reconciliation view (/financial/reconciliation/):
    Table of card transactions with filtering, sorting, pagination, fee breakdown, dynamic totalizers, and bulk actions.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    brand_filter = request.GET.get('brand', '').strip()
    tx_type_filter = request.GET.get('transaction_type', '').strip()
    sort_param = request.GET.get('sort', '').strip()
    page_number = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 10))

    reconciliations = CardReconciliation.objects.all()

    if query:
        reconciliations = reconciliations.filter(Q(sale__sale_code__icontains=query) | Q(sale__customer_name__icontains=query))
    if status_filter:
        reconciliations = reconciliations.filter(status=status_filter)
    if brand_filter:
        reconciliations = reconciliations.filter(card_brand=brand_filter)
    if tx_type_filter:
        reconciliations = reconciliations.filter(transaction_type=tx_type_filter)

    # Sorting
    if sort_param:
        clean_field = sort_param.lstrip('-')
        if clean_field in ALLOWED_RECONCILIATION_SORT:
            reconciliations = reconciliations.order_by(sort_param)
        else:
            reconciliations = reconciliations.order_by('-created_at')
    else:
        reconciliations = reconciliations.order_by('-created_at')

    # Aggregates across filtered QS
    total_count = reconciliations.count()
    total_gross = reconciliations.aggregate(total=Sum('gross_amount'))['total'] or Decimal('0.00')
    total_fees = reconciliations.aggregate(total=Sum('fee_amount'))['total'] or Decimal('0.00')
    total_net = reconciliations.aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')
    
    total_gross_sales = total_gross
    total_mdr_fees = total_fees
    total_net_amount = total_net

    # Pagination
    paginator = Paginator(reconciliations, per_page)
    page_obj = paginator.get_page(page_number)

    context = {
        'reconciliations': page_obj,
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'brand_filter': brand_filter,
        'tx_type_filter': tx_type_filter,
        'current_sort': sort_param,
        'total_gross': round(total_gross, 2),
        'total_fees': round(total_fees, 2),
        'total_net': round(total_net, 2),
        'total_gross_sales': round(total_gross_sales, 2),
        'total_mdr_fees': round(total_mdr_fees, 2),
        'total_net_amount': round(total_net_amount, 2),
        'total_count': total_count,
        'per_page': per_page,
    }

    if request.headers.get('HX-Request') or request.GET.get('table_only'):
        return render(request, 'financial/partials/reconciliation_table.html', context)

    return render(request, 'financial/reconciliation_list.html', context)


def reconciliation_bulk_action(request):
    """
    HTMX Endpoint for bulk operations on card reconciliation (mark status: conciliado, pendente, divergente, delete).
    """
    if request.method == 'POST':
        action = request.POST.get('bulk_action', '').strip()
        selected_ids = request.POST.getlist('selected_ids')

        if selected_ids and action:
            selected_recs = CardReconciliation.objects.filter(id__in=selected_ids)
            if action in ['conciliado', 'pendente', 'divergente']:
                selected_recs.update(status=action)
                messages.success(request, f"{selected_recs.count()} transações de cartão atualizadas para {action}.")
            elif action == 'delete':
                count = selected_recs.count()
                selected_recs.delete()
                messages.success(request, f"{count} transações de cartão excluídas.")

    return reconciliation_list(request)


def reconciliation_toggle_status(request, pk):
    """
    HTMX endpoint to toggle card reconciliation status (pendente -> conciliado -> divergente -> pendente).
    """
    rec = get_object_or_404(CardReconciliation, pk=pk)
    if request.method == 'POST':
        next_status = request.POST.get('status')
        if next_status in ['pendente', 'conciliado', 'divergente']:
            rec.status = next_status
        else:
            status_cycle = {'pendente': 'conciliado', 'conciliado': 'divergente', 'divergente': 'pendente'}
            rec.status = status_cycle.get(rec.status, 'conciliado')
        rec.save()

    if request.headers.get('HX-Request'):
        return render(request, 'financial/partials/reconciliation_row.html', {'rec': rec})
    return redirect('financial:reconciliation_list')

