from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from inventory.models import Product, Category
from catalog.models import ProductImage, BarcodeLabelTemplate
from catalog.utils import (
    normalize_barcode,
    generate_barcode_svg,
    generate_qr_code_svg,
    generate_elgin_tspl_label,
    generate_elgin_epl_label,
    generate_elgin_zpl_label,
)

def visual_catalog(request):
    """
    Visual Photo Catalog view with HTMX dynamic filtering by category, size, color, search query, and stock status.
    """
    products_qs = Product.objects.prefetch_related('images').all().order_by('-id')

    # Extract filter options
    categories = list(Product.objects.exclude(categoria='').values_list('categoria', flat=True).distinct())
    sizes = list(Product.objects.exclude(tamanho='').values_list('tamanho', flat=True).distinct())
    colors = list(Product.objects.exclude(cor='').values_list('cor', flat=True).distinct())

    selected_category = request.GET.get('category', '').strip()
    selected_size = request.GET.get('size', '').strip()
    selected_color = request.GET.get('color', '').strip()
    selected_stock = request.GET.get('stock', '').strip()
    search_query = request.GET.get('q', '').strip()

    # Apply filters
    if selected_category:
        products_qs = products_qs.filter(Q(categoria__iexact=selected_category) | Q(category_obj__name__iexact=selected_category))

    if selected_size:
        products_qs = products_qs.filter(tamanho__iexact=selected_size)

    if selected_color:
        products_qs = products_qs.filter(cor__iexact=selected_color)

    if search_query:
        products_qs = products_qs.filter(
            Q(cod_unico__icontains=search_query) |
            Q(descricao__icontains=search_query) |
            Q(cor__icontains=search_query)
        )

    if selected_stock == 'in_stock':
        products_qs = products_qs.filter(quantidade__gt=3)
    elif selected_stock == 'low_stock':
        products_qs = products_qs.filter(quantidade__gte=1, quantidade__lte=3)
    elif selected_stock == 'out_of_stock':
        products_qs = products_qs.filter(quantidade__lte=0)

    # Compute stock statistics
    total_products = Product.objects.count()
    in_stock_count = Product.objects.filter(quantidade__gt=3).count()
    low_stock_count = Product.objects.filter(quantidade__gte=1, quantidade__lte=3).count()
    out_of_stock_count = Product.objects.filter(quantidade__lte=0).count()

    context = {
        'products': products_qs,
        'categories': sorted(categories),
        'sizes': sorted(sizes),
        'colors': sorted(colors),
        'selected_category': selected_category,
        'selected_size': selected_size,
        'selected_color': selected_color,
        'selected_stock': selected_stock,
        'search_query': search_query,
        'stats': {
            'total': total_products,
            'in_stock': in_stock_count,
            'low_stock': low_stock_count,
            'out_of_stock': out_of_stock_count,
        }
    }

    if request.headers.get('HX-Request') or request.GET.get('partial') == '1':
        return render(request, 'catalog/partials/product_grid.html', context)

    return render(request, 'catalog/visual_catalog.html', context)


def quick_view_modal(request, code_or_id):
    """
    HTMX Modal view for product quick view details.
    """
    if str(code_or_id).isdigit():
        product = get_object_or_404(Product, id=int(code_or_id))
    else:
        product = get_object_or_404(Product, cod_unico=code_or_id)

    barcode_svg = generate_barcode_svg(product.cod_unico, width=220, height=70)
    qr_svg = generate_qr_code_svg(product.cod_unico, size=120)
    tspl_command = generate_elgin_tspl_label(product.cod_unico, product.descricao, product.preco_venda)

    context = {
        'product': product,
        'barcode_svg': barcode_svg,
        'qr_svg': qr_svg,
        'tspl_command': tspl_command,
    }
    return render(request, 'catalog/partials/quick_view_modal.html', context)


def scanner_view(request):
    """
    Web Camera and USB Barcode/QR Scanner Interface.
    """
    return render(request, 'catalog/scanner.html', {
        'title': 'Leitor de Código de Barras & QR Code'
    })


def scan_lookup_view(request, code_unico=None):
    """
    HTMX endpoint for barcode/QR code lookup.
    """
    if not code_unico:
        code_unico = request.GET.get('code', '').strip()

    normalized_code = normalize_barcode(code_unico)

    product = None
    if normalized_code:
        # Search by exact code, iexact, or lstripped zeros
        product = Product.objects.filter(cod_unico=normalized_code).first()
        if not product:
            product = Product.objects.filter(cod_unico__iexact=normalized_code).first()
        if not product and normalized_code.startswith('0'):
            product = Product.objects.filter(cod_unico=normalized_code.lstrip('0')).first()

    if product:
        barcode_svg = generate_barcode_svg(product.cod_unico, width=220, height=70)
        qr_svg = generate_qr_code_svg(product.cod_unico, size=100)
        tspl_command = generate_elgin_tspl_label(product.cod_unico, product.descricao, product.preco_venda)
        context = {
            'found': True,
            'product': product,
            'scanned_code': normalized_code,
            'barcode_svg': barcode_svg,
            'qr_svg': qr_svg,
            'tspl_command': tspl_command,
        }
    else:
        context = {
            'found': False,
            'scanned_code': normalized_code or code_unico or 'N/A',
        }

    return render(request, 'catalog/partials/scan_lookup_result.html', context)


def label_generator_view(request):
    """
    Elgin L42PRO Label Generator page.
    """
    products = Product.objects.all().order_by('cod_unico')
    templates = BarcodeLabelTemplate.objects.all()

    return render(request, 'catalog/label_generator.html', {
        'products': products,
        'templates': templates,
    })


def label_preview_view(request):
    """
    Label Preview endpoint returning TSPL / EPL / ZPL code strings and HTML print preview.
    """
    product_ids = request.POST.getlist('product_ids') or request.GET.getlist('product_ids')
    single_code = request.GET.get('code') or request.POST.get('code')

    printer_type = request.POST.get('printer_type') or request.GET.get('printer_type') or 'ELGIN_L42PRO'
    label_format = request.POST.get('label_format') or request.GET.get('label_format') or '50x30'

    width_mm = 50 if label_format == '50x30' else 40
    height_mm = 30 if label_format == '50x30' else 25

    items_to_print = []

    if single_code:
        product = Product.objects.filter(cod_unico=single_code).first()
        if product:
            qty = int(request.GET.get('qty') or request.POST.get('qty') or 1)
            items_to_print.append({'product': product, 'quantity': qty})
    elif product_ids:
        for pid in product_ids:
            qty = int(request.POST.get(f'qty_{pid}') or request.GET.get(f'qty_{pid}') or 1)
            product = Product.objects.filter(id=pid).first()
            if product:
                items_to_print.append({'product': product, 'quantity': qty})
    else:
        # Fallback to first few products for demo
        for product in Product.objects.all()[:3]:
            items_to_print.append({'product': product, 'quantity': 1})

    # Build TSPL, EPL, ZPL command strings and HTML items
    tspl_all = []
    epl_all = []
    zpl_all = []
    html_items = []

    for item in items_to_print:
        p = item['product']
        q = item['quantity']

        tspl_cmd = generate_elgin_tspl_label(p.cod_unico, p.descricao, p.preco_venda, width_mm=width_mm, height_mm=height_mm, quantity=q)
        epl_cmd = generate_elgin_epl_label(p.cod_unico, p.descricao, p.preco_venda, quantity=q)
        zpl_cmd = generate_elgin_zpl_label(p.cod_unico, p.descricao, p.preco_venda, quantity=q)

        tspl_all.append(tspl_cmd)
        epl_all.append(epl_cmd)
        zpl_all.append(zpl_cmd)

        barcode_svg = generate_barcode_svg(p.cod_unico, width=180, height=50)
        qr_svg = generate_qr_code_svg(p.cod_unico, size=70)

        for _ in range(q):
            html_items.append({
                'product': p,
                'barcode_svg': barcode_svg,
                'qr_svg': qr_svg,
                'width_mm': width_mm,
                'height_mm': height_mm,
            })

    tspl_string = "\n\n".join(tspl_all)
    epl_string = "\n\n".join(epl_all)
    zpl_string = "\n\n".join(zpl_all)

    context = {
        'items': items_to_print,
        'html_items': html_items,
        'tspl_string': tspl_string,
        'epl_string': epl_string,
        'zpl_string': zpl_string,
        'printer_type': printer_type,
        'width_mm': width_mm,
        'height_mm': height_mm,
    }

    if request.headers.get('HX-Request') or request.GET.get('partial') == '1':
        return render(request, 'catalog/partials/label_preview_content.html', context)

    return render(request, 'catalog/label_preview.html', context)


def label_print_view(request):
    """
    Direct printable endpoint / TSPL output file download.
    """
    mode = request.GET.get('mode', 'html')
    code = request.GET.get('code')
    product_ids = request.GET.getlist('product_ids')
    qty = int(request.GET.get('qty', 1))

    products = []
    if code:
        p = Product.objects.filter(cod_unico=code).first()
        if p:
            products.append((p, qty))
    elif product_ids:
        for pid in product_ids:
            p = Product.objects.filter(id=pid).first()
            if p:
                products.append((p, qty))
    else:
        for p in Product.objects.all()[:5]:
            products.append((p, 1))

    if mode == 'tspl':
        tspl_parts = []
        for p, q in products:
            tspl_parts.append(generate_elgin_tspl_label(p.cod_unico, p.descricao, p.preco_venda, quantity=q))
        content = "\n\n".join(tspl_parts)
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="etiquetas_elgin_l42pro.tspl"'
        return response

    # Default HTML printable label sheet
    html_items = []
    for p, q in products:
        barcode_svg = generate_barcode_svg(p.cod_unico, width=180, height=50)
        qr_svg = generate_qr_code_svg(p.cod_unico, size=70)
        for _ in range(q):
            html_items.append({
                'product': p,
                'barcode_svg': barcode_svg,
                'qr_svg': qr_svg,
            })

    return render(request, 'catalog/label_print_sheet.html', {
        'html_items': html_items,
        'auto_print': True
    })
