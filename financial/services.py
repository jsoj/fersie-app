from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from inventory.models import Product, StockTransaction
from .models import (
    Supplier, Purchase, PurchaseItem,
    Sale, SaleItem, Expense, AccountsReceivable, CardReconciliation
)

def get_card_fee_config(transaction_type, installment_count=1):
    """
    Returns (fee_percentage, settlement_days) based on transaction_type.
    MDR Rates:
      - debito: 1.99% (settlement in 1 day)
      - credito_avista: 3.49% (settlement in 30 days)
      - credito_parcelado: 4.99% (settlement in 30 days)
    """
    tt = (transaction_type or '').lower()
    if tt in ['debito', 'debit']:
        return Decimal('1.99'), 1
    elif tt in ['credito_avista', 'credit_1x']:
        return Decimal('3.49'), 30
    elif tt in ['credito_parcelado', 'credit_mx']:
        if installment_count and installment_count >= 7:
            return Decimal('5.20'), 30
        return Decimal('4.99'), 30
    else:
        # Fallback default
        return Decimal('3.49'), 30

@transaction.atomic
def process_sale_checkout(
    customer_name="",
    sale_type="balcao",
    payment_method="dinheiro",
    discount=Decimal("0.00"),
    items=None,
    card_brand="visa",
    transaction_type=None,
    installment_count=1
):
    """
    Executes a complete Sale checkout:
    1. Validates product stock availability.
    2. Creates Sale and SaleItem records.
    3. Deducts stock_quantity on each Product and creates StockTransaction (Saída).
    4. Generates CardReconciliation if payment_method is card.
    5. Generates AccountsReceivable.
    """
    if not items:
        raise ValueError("A venda deve conter ao menos um produto.")

    discount = Decimal(str(discount or 0))

    # Pre-validate stock for all items before any modifications
    validated_items = []
    gross_amount = Decimal("0.00")

    for item in items:
        prod_id = item.get("product_id") or item.get("product").id
        qty = int(item.get("quantity", 1))
        unit_price = Decimal(str(item.get("unit_price", 0)))

        if qty <= 0:
            raise ValueError("A quantidade do produto deve ser maior que zero.")

        product = Product.objects.select_for_update().get(id=prod_id)
        current_stock = product.quantidade

        if current_stock < qty:
            raise ValueError(
                f"Estoque insuficiente para '{product.descricao}'. "
                f"Disponível: {current_stock}, Solicitado: {qty}"
            )

        item_total = unit_price * Decimal(str(qty))
        gross_amount += item_total
        validated_items.append({
            "product": product,
            "quantity": qty,
            "unit_price": unit_price,
            "total_price": item_total
        })

    net_amount = max(Decimal("0.00"), gross_amount - discount)

    # Normalize payment method
    pm = (payment_method or 'dinheiro').lower()
    if pm in ['credit', 'cartao_credito']:
        pm = 'cartao_credito'
    elif pm in ['debit', 'cartao_debito']:
        pm = 'cartao_debito'
    elif pm in ['cash', 'dinheiro']:
        pm = 'dinheiro'
    elif pm in ['pix']:
        pm = 'pix'

    sale = Sale.objects.create(
        customer_name=customer_name or "Cliente Balcão",
        sale_type=sale_type,
        payment_method=pm,
        gross_amount=gross_amount,
        discount=discount,
        net_amount=net_amount,
        status='completed',
        date=timezone.now().date(),
        # For legacy compatibility, set product/quantity/unit_price from first item
        product=validated_items[0]["product"] if validated_items else None,
        quantity=validated_items[0]["quantity"] if validated_items else 1,
        unit_price=validated_items[0]["unit_price"] if validated_items else Decimal("0.00")
    )

    # Save items and deduct stock
    for vitem in validated_items:
        product = vitem["product"]
        qty = vitem["quantity"]

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=qty,
            unit_price=vitem["unit_price"],
            total_price=vitem["total_price"]
        )

        # Deduct stock
        product.quantidade -= qty
        product.save()

        # Log stock movement
        StockTransaction.objects.create(
            product=product,
            transaction_type='OUT',
            quantity=qty,
            unit_price=vitem["unit_price"],
            notes=f"Venda {sale.sale_code}"
        )

    # Handle Card Reconciliation for Card Sales
    if pm in ['cartao_credito', 'cartao_debito']:
        if not transaction_type:
            transaction_type = 'debito' if pm == 'cartao_debito' else ('credito_parcelado' if installment_count > 1 else 'credito_avista')

        fee_pct, days = get_card_fee_config(transaction_type, installment_count)
        fee_amt = round(net_amount * (fee_pct / Decimal('100.0')), 2)
        net_settlement = net_amount - fee_amt
        settlement_date = sale.date + timedelta(days=days)

        CardReconciliation.objects.create(
            sale=sale,
            card_brand=card_brand,
            transaction_type=transaction_type,
            gross_amount=net_amount,
            fee_percentage=fee_pct,
            fee_amount=fee_amt,
            net_amount=net_settlement,
            expected_settlement_date=settlement_date,
            status='pendente'
        )

        # Record Accounts Receivable for card settlement
        AccountsReceivable.objects.create(
            sale=sale,
            customer_name=sale.customer_name,
            description=f"Repasse Cartão ({transaction_type}) — Venda {sale.sale_code}",
            total_amount=net_settlement,
            due_date=settlement_date,
            status='pendente',
            payment_method=pm
        )
    else:
        # Cash/PIX sale -> immediate receivable settlement
        AccountsReceivable.objects.create(
            sale=sale,
            customer_name=sale.customer_name,
            description=f"Venda {sale.sale_code} ({pm.upper()})",
            total_amount=net_amount,
            due_date=sale.date,
            status='pago',
            payment_method=pm,
            received_amount=net_amount,
            received_date=sale.date
        )

    return sale


@transaction.atomic
def process_purchase_ingestion(
    supplier,
    invoice_number="",
    status="pending",
    notes="",
    items=None,
    date=None
):
    """
    Registers a Purchase and updates product stock quantities:
    1. Creates Purchase and PurchaseItem records.
    2. Increments stock_quantity on each Product and creates StockTransaction (Entrada).
    """
    if not items:
        raise ValueError("A compra deve conter ao menos um item.")

    purchase_date = date or timezone.now().date()
    total_amount = Decimal("0.00")
    prepared_items = []

    for item in items:
        prod_id = item.get("product_id") or item.get("product").id
        qty = int(item.get("quantity", 1))
        unit_cost = Decimal(str(item.get("unit_cost", 0)))

        if qty <= 0:
            raise ValueError("A quantidade do item de compra deve ser maior que zero.")

        product = Product.objects.select_for_update().get(id=prod_id)
        item_total = unit_cost * Decimal(str(qty))
        total_amount += item_total

        prepared_items.append({
            "product": product,
            "quantity": qty,
            "unit_cost": unit_cost,
            "total_cost": item_total
        })

    purchase = Purchase.objects.create(
        supplier=supplier,
        invoice_number=invoice_number,
        date=purchase_date,
        total_amount=total_amount,
        status=status,
        notes=notes
    )

    for pitem in prepared_items:
        product = pitem["product"]
        qty = pitem["quantity"]

        PurchaseItem.objects.create(
            purchase=purchase,
            product=product,
            quantity=qty,
            unit_cost=pitem["unit_cost"],
            total_cost=pitem["total_cost"]
        )

        # Increment stock quantity
        product.quantidade += qty
        product.save()

        # Record stock movement (IN)
        StockTransaction.objects.create(
            product=product,
            transaction_type='IN',
            quantity=qty,
            unit_price=pitem["unit_cost"],
            notes=f"Entrada NF {invoice_number or purchase.id} - Fornecedor {supplier.name}"
        )

    return purchase
