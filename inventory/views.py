from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Sum, Q
from django.core.paginator import Paginator
from django.contrib import messages
from .models import Product, Supplier, Category, StockTransaction

ALLOWED_PRODUCT_SORT_FIELDS = {
    'cod_unico', 'code', 'descricao', 'name', 'cor', 'tamanho',
    'preco_custo', 'cost_price', 'preco_venda', 'sale_price',
    'quantidade', 'stock_quantity', 'categoria', 'fornecedor__name'
}

SORT_FIELD_MAP = {
    'code': 'cod_unico',
    'name': 'descricao',
    'cost_price': 'preco_custo',
    'sale_price': 'preco_venda',
    'stock_quantity': 'quantidade',
}

def product_list(request):
    q = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    stock_status_filter = request.GET.get('stock_status', '').strip()
    sort_param = request.GET.get('sort', '').strip()
    page_number = request.GET.get('page', 1)
    per_page = int(request.GET.get('per_page', 10))

    products = Product.objects.all()

    if q:
        products = products.filter(
            Q(cod_unico__icontains=q) |
            Q(descricao__icontains=q) |
            Q(categoria__icontains=q) |
            Q(cor__icontains=q) |
            Q(tamanho__icontains=q) |
            Q(fornecedor__name__icontains=q)
        )

    if category_filter:
        products = products.filter(Q(categoria__iexact=category_filter) | Q(category_obj__name__iexact=category_filter))

    if stock_status_filter == 'in_stock':
        products = products.filter(quantidade__gt=3)
    elif stock_status_filter == 'low_stock':
        products = products.filter(quantidade__gte=1, quantidade__lte=3)
    elif stock_status_filter == 'out_of_stock':
        products = products.filter(quantidade__lte=0)

    # Apply sorting
    if sort_param:
        is_desc = sort_param.startswith('-')
        clean_field = sort_param.lstrip('-')
        actual_field = SORT_FIELD_MAP.get(clean_field, clean_field)
        if actual_field in ALLOWED_PRODUCT_SORT_FIELDS or clean_field in ALLOWED_PRODUCT_SORT_FIELDS:
            sort_expression = f"-{actual_field}" if is_desc else actual_field
            products = products.order_by(sort_expression)
        else:
            products = products.order_by('cod_unico')
    else:
        products = products.order_by('cod_unico')

    # Totalizers across ALL filtered products (not just paginated slice)
    total_qty = products.aggregate(Sum('quantidade'))['quantidade__sum'] or 0
    total_cost = sum((p.preco_custo or Decimal('0.00')) * (p.quantidade or 0) for p in products)
    total_value = sum((p.preco_venda or Decimal('0.00')) * (p.quantidade or 0) for p in products)
    total_profit = total_value - total_cost

    # Pagination
    paginator = Paginator(products, per_page)
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all()

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'total_qty': total_qty,
        'total_cost': round(total_cost, 2),
        'total_value': round(total_value, 2),
        'total_profit': round(total_profit, 2),
        'q': q,
        'categories': categories,
        'selected_category': category_filter,
        'selected_stock_status': stock_status_filter,
        'current_sort': sort_param,
        'per_page': per_page,
    }

    if request.headers.get('HX-Request') or request.GET.get('table_only'):
        return render(request, 'components/htmx_totalizer_table.html', context)

    return render(request, 'inventory/product_list.html', context)


def product_bulk_action(request):
    """
    HTMX Endpoint for bulk operations on inventory products (delete, stock adjustment).
    """
    if request.method == 'POST':
        action = request.POST.get('bulk_action', '').strip()
        selected_ids = request.POST.getlist('selected_ids')

        if selected_ids and action:
            selected_products = Product.objects.filter(id__in=selected_ids)
            if action == 'delete':
                count = selected_products.count()
                selected_products.delete()
                messages.success(request, f"{count} produtos excluídos com sucesso.")
            elif action == 'adjust_stock_add':
                for p in selected_products:
                    p.quantidade += 1
                    p.save()
                messages.success(request, "Estoque incrementado em +1 para os produtos selecionados.")
            elif action == 'adjust_stock_remove':
                for p in selected_products:
                    p.quantidade = max(0, p.quantidade - 1)
                    p.save()
                messages.success(request, "Estoque decrementado em -1 para os produtos selecionados.")
            elif action == 'zero_stock':
                for p in selected_products:
                    p.quantidade = 0
                    p.save()
                messages.success(request, "Estoque zerado para os produtos selecionados.")

    return product_list(request)


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    transactions = product.transactions.all().order_by('-created_at')
    return render(request, 'inventory/product_detail.html', {
        'product': product,
        'transactions': transactions,
    })


def public_products_api(request):
    """
    Public API consumed by fersie.com: returns all products marked with exibir_no_site=True,
    including photos, prices, categories, and inventory status.
    """
    products = Product.objects.filter(exibir_no_site=True).prefetch_related('images')
    data = []
    for p in products:
        images = []
        for img in p.images.all():
            if img.image:
                images.append(request.build_absolute_uri(img.image.url))
        data.append({
            'code': p.cod_unico,
            'name': p.descricao,
            'color': p.cor,
            'size': p.tamanho,
            'category': p.categoria,
            'price': str(p.preco_venda),
            'in_stock': p.quantidade > 0,
            'featured': p.destaque_vitrine,
            'images': images,
            'image_url': images[0] if images else None,
        })
    response = JsonResponse({'count': len(data), 'results': data})
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    return response

