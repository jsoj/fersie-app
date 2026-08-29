from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse

from inventory.models import Product, StockTransaction
from financial.models import (
    Supplier, Purchase, PurchaseItem,
    Sale, SaleItem, Expense, AccountsReceivable, CardReconciliation
)
from financial.services import process_sale_checkout, process_purchase_ingestion, get_card_fee_config


class FinancialModelsAndServicesTest(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(
            name="Confecções Fersie LTDA",
            cnpj_cpf="12.345.678/0001-90",
            phone="(11) 98888-7777",
            email="contato@fersie.com.br"
        )

        self.product_1 = Product.objects.create(
            cod_unico="FER-VET-01",
            descricao="Vestido Linho Fersie",
            preco_custo=Decimal("80.00"),
            preco_venda=Decimal("250.00"),
            quantidade=15
        )

        self.product_2 = Product.objects.create(
            cod_unico="FER-BLU-02",
            descricao="Blusa Seda Gold",
            preco_custo=Decimal("45.00"),
            preco_venda=Decimal("120.00"),
            quantidade=5
        )

    def test_supplier_creation(self):
        self.assertEqual(str(self.supplier), "Confecções Fersie LTDA")
        self.assertEqual(self.supplier.cnpj_cpf, "12.345.678/0001-90")

    def test_purchase_ingestion_stock_increment(self):
        initial_stock = self.product_1.quantidade
        items = [{
            'product_id': self.product_1.id,
            'quantity': 10,
            'unit_cost': Decimal("75.00")
        }]

        purchase = process_purchase_ingestion(
            supplier=self.supplier,
            invoice_number="NF-2026-001",
            status="paid",
            notes="Lote de Primavera",
            items=items
        )

        self.product_1.refresh_from_db()
        self.assertEqual(purchase.total_amount, Decimal("750.00"))
        self.assertEqual(self.product_1.quantidade, initial_stock + 10)
        
        # Verify stock movement entry
        tx = StockTransaction.objects.filter(product=self.product_1, transaction_type='IN').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.quantity, 10)

    def test_sale_checkout_stock_deduction(self):
        initial_stock = self.product_1.quantidade
        items = [{
            'product_id': self.product_1.id,
            'quantity': 3,
            'unit_price': Decimal("250.00")
        }]

        sale = process_sale_checkout(
            customer_name="Fernanda Lima",
            sale_type="balcao",
            payment_method="dinheiro",
            discount=Decimal("50.00"),
            items=items
        )

        self.product_1.refresh_from_db()
        self.assertEqual(sale.gross_amount, Decimal("750.00"))
        self.assertEqual(sale.discount, Decimal("50.00"))
        self.assertEqual(sale.net_amount, Decimal("700.00"))
        self.assertEqual(self.product_1.quantidade, initial_stock - 3)

        # Verify stock movement entry
        tx = StockTransaction.objects.filter(product=self.product_1, transaction_type='OUT').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.quantity, 3)

        # Verify immediate cash receivable entry
        rec = AccountsReceivable.objects.filter(sale=sale).first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, 'pago')

    def test_sale_checkout_insufficient_stock_error(self):
        items = [{
            'product_id': self.product_2.id,
            'quantity': 20, # Only 5 available
            'unit_price': Decimal("120.00")
        }]

        with self.assertRaises(ValueError) as ctx:
            process_sale_checkout(
                customer_name="Cliente Excesso",
                items=items
            )
        self.assertIn("Estoque insuficiente", str(ctx.exception))

    def test_card_reconciliation_calculation(self):
        items = [{
            'product_id': self.product_1.id,
            'quantity': 2,
            'unit_price': Decimal("250.00")
        }]

        # Credit sale: R$ 500.00 gross, 3.49% fee
        sale = process_sale_checkout(
            customer_name="Patricia Amorim",
            sale_type="online",
            payment_method="cartao_credito",
            card_brand="mastercard",
            transaction_type="credito_avista",
            items=items
        )

        rec = CardReconciliation.objects.get(sale=sale)
        self.assertEqual(rec.card_brand, "mastercard")
        self.assertEqual(rec.transaction_type, "credito_avista")
        self.assertEqual(rec.gross_amount, Decimal("500.00"))
        self.assertEqual(rec.fee_percentage, Decimal("3.49"))
        self.assertEqual(rec.fee_amount, Decimal("17.45")) # 500 * 0.0349
        self.assertEqual(rec.net_amount, Decimal("482.55")) # 500 - 17.45
        self.assertEqual(rec.status, "pendente")
        self.assertEqual(rec.expected_settlement_date, sale.date + timedelta(days=30))

        # Check pending receivable record for card payout
        ar = AccountsReceivable.objects.get(sale=sale)
        self.assertEqual(ar.status, "pendente")
        self.assertEqual(ar.total_amount, Decimal("482.55"))

    def test_expense_creation_and_mark_paid(self):
        expense = Expense.objects.create(
            description="Energia Elétrica Loja",
            category="operacional",
            amount=Decimal("420.00"),
            due_date=date.today(),
            status="pendente"
        )

        self.assertFalse(expense.is_paid)
        self.assertEqual(expense.status, "pendente")

        expense.is_paid = True
        expense.save()
        self.assertEqual(expense.status, "pago")


class FinancialViewsAndTemplatesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.supplier = Supplier.objects.create(name="Fornecedor Principal")
        self.product = Product.objects.create(
            cod_unico="FER-TST-99",
            descricao="Produto Teste View",
            preco_custo=Decimal("10.00"),
            preco_venda=Decimal("30.00"),
            quantidade=20
        )

    def test_overview_view(self):
        url = reverse('financial:overview')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'financial/overview.html')
        self.assertContains(response, "Controle Comercial & Financeiro")
        self.assertContains(response, "Total de Vendas")
        self.assertContains(response, "fersie-totalizer-row")

    def test_sales_list_view(self):
        url = reverse('financial:sales_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'financial/sales_list.html')
        self.assertContains(response, "Histórico de Vendas")
        self.assertContains(response, "fersie-totalizer-row")

    def test_sales_create_view_get_and_post(self):
        url = reverse('financial:sales_create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'financial/sales_create.html')

        post_data = {
            'customer_name': 'Cliente Teste HTTP',
            'sale_type': 'balcao',
            'payment_method': 'dinheiro',
            'discount': '5.00',
            'product_id': [self.product.id],
            'quantity': [2],
            'unit_price': ['30.00']
        }
        post_response = self.client.post(url, post_data)
        self.assertEqual(post_response.status_code, 302) # Redirect to sales_list

        self.product.refresh_from_db()
        self.assertEqual(self.product.quantidade, 18)

    def test_purchases_list_view(self):
        url = reverse('financial:purchases_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'financial/purchases_list.html')
        self.assertContains(response, "Gestão de Compras")

    def test_expenses_list_view_and_mark_paid(self):
        url = reverse('financial:expenses_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'financial/expenses_list.html')

        # Create expense via POST
        post_data = {
            'description': 'Taxa de Condomínio',
            'category': 'aluguel',
            'amount': '300.00',
            'due_date': '2026-09-10',
            'status': 'pendente'
        }
        self.client.post(url, post_data)
        expense = Expense.objects.get(description='Taxa de Condomínio')
        self.assertEqual(expense.amount, Decimal("300.00"))

        # Mark paid via HTMX endpoint
        mark_url = reverse('financial:expense_mark_paid', kwargs={'pk': expense.pk})
        htmx_response = self.client.post(mark_url, HTTP_HX_REQUEST='true')
        self.assertEqual(htmx_response.status_code, 200)
        expense.refresh_from_db()
        self.assertEqual(expense.status, 'pago')

    def test_receivables_list_view(self):
        url = reverse('financial:receivables_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'financial/receivables_list.html')

    def test_reconciliation_list_view(self):
        url = reverse('financial:reconciliation_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'financial/reconciliation_list.html')

    def test_financial_bulk_actions_and_sorting(self):
        """Test bulk actions and sorting for sales, purchases, expenses, receivables, and reconciliation."""
        # 1. Sales bulk action
        s1 = Sale.objects.create(sale_code="S-001", customer_name="Ana", gross_amount=100, net_amount=100, status="completed")
        s2 = Sale.objects.create(sale_code="S-002", customer_name="Bia", gross_amount=200, net_amount=200, status="completed")
        
        sales_bulk_url = reverse('financial:sales_bulk_action')
        resp = self.client.post(sales_bulk_url, {'selected_ids': [s1.id, s2.id], 'bulk_action': 'cancelled'})
        self.assertEqual(resp.status_code, 200)
        s1.refresh_from_db()
        self.assertEqual(s1.status, 'cancelled')

        # 2. Purchases bulk action
        p1 = Purchase.objects.create(supplier=self.supplier, total_amount=500, status="pending")
        purch_bulk_url = reverse('financial:purchases_bulk_action')
        resp_p = self.client.post(purch_bulk_url, {'selected_ids': [p1.id], 'bulk_action': 'mark_paid'})
        self.assertEqual(resp_p.status_code, 200)
        p1.refresh_from_db()
        self.assertEqual(p1.status, 'paid')

        # 3. Expenses bulk action
        e1 = Expense.objects.create(description="Aluguel", category="aluguel", amount=1000, due_date="2026-09-01", status="pendente")
        exp_bulk_url = reverse('financial:expenses_bulk_action')
        resp_e = self.client.post(exp_bulk_url, {'selected_ids': [e1.id], 'bulk_action': 'mark_paid'})
        self.assertEqual(resp_e.status_code, 200)
        e1.refresh_from_db()
        self.assertEqual(e1.status, 'pago')

        # 4. Receivables bulk action
        r1 = AccountsReceivable.objects.create(customer_name="Carla", total_amount=150, status="pendente")
        rec_bulk_url = reverse('financial:receivables_bulk_action')
        resp_r = self.client.post(rec_bulk_url, {'selected_ids': [r1.id], 'bulk_action': 'mark_paid'})
        self.assertEqual(resp_r.status_code, 200)
        r1.refresh_from_db()
        self.assertEqual(r1.status, 'pago')

        # 5. Reconciliation bulk action
        c1 = CardReconciliation.objects.create(sale=s1, card_brand="visa", transaction_type="debito", gross_amount=100, fee_percentage=1, fee_amount=1, net_amount=99, status="pendente")
        recon_bulk_url = reverse('financial:reconciliation_bulk_action')
        resp_c = self.client.post(recon_bulk_url, {'selected_ids': [c1.id], 'bulk_action': 'conciliado'})
        self.assertEqual(resp_c.status_code, 200)
        c1.refresh_from_db()
        self.assertEqual(c1.status, 'conciliado')

    def test_totalizer_rows_rendering(self):
        """Test that fersie-totalizer-row is present in all financial table lists."""
        for view_name in ['sales_list', 'purchases_list', 'expenses_list', 'receivables_list', 'reconciliation_list']:
            url = reverse(f'financial:{view_name}')
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, 'fersie-totalizer-row')

