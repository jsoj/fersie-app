import os
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from inventory.models import Product, Supplier, Category, StockTransaction

EXCEL_FILE_PATH = "/home/jsoj/fersie/Planilha Mercadoria_JUNIOR_v2.xlsx"

class ExcelMerchandiseImportTest(TestCase):
    def test_import_excel_merchandise_command(self):
        """Test import_excel_merchandise command successfully ingests merchandise spreadsheet."""
        if not os.path.exists(EXCEL_FILE_PATH):
            self.skipTest(f"Spreadsheet file not found at {EXCEL_FILE_PATH}")

        call_command('import_excel_merchandise', file=EXCEL_FILE_PATH)
        product_count = Product.objects.count()
        self.assertGreater(product_count, 0, "Excel ingestion should populate products in database.")

        first_product = Product.objects.first()
        self.assertIsNotNone(first_product.cod_unico)
        self.assertIsNotNone(first_product.descricao)
        self.assertGreaterEqual(first_product.preco_venda, Decimal("0.00"))

    def test_import_excel_merchandise_idempotency(self):
        """Test import_excel_merchandise is idempotent across multiple runs."""
        if not os.path.exists(EXCEL_FILE_PATH):
            self.skipTest(f"Spreadsheet file not found at {EXCEL_FILE_PATH}")

        call_command('import_excel_merchandise', file=EXCEL_FILE_PATH)
        count_run_1 = Product.objects.count()
        call_command('import_excel_merchandise', file=EXCEL_FILE_PATH)
        count_run_2 = Product.objects.count()
        self.assertEqual(count_run_1, count_run_2, "Repeated imports must not create duplicate products.")

class InventoryModelsAndViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="Alfaiataria", description="Peças de alta alfaiataria")
        self.supplier = Supplier.objects.create(name="Confecção Fersie", contact_name="Maria", phone="11988887777")
        self.product = Product.objects.create(
            cod_unico="FER-101",
            descricao="Blazer Alfaiataria Gold",
            cor="Preto",
            tamanho="M",
            preco_custo=Decimal("120.00"),
            preco_venda=Decimal("299.90"),
            quantidade=5,
            categoria="Alfaiataria",
            category_obj=self.category,
            fornecedor=self.supplier
        )

    def test_product_schema_properties(self):
        """Test property getters and setters for English/Portuguese schema compatibility."""
        self.assertEqual(self.product.code, "FER-101")
        self.assertEqual(self.product.barcode, "FER-101")
        self.assertEqual(self.product.name, "Blazer Alfaiataria Gold")
        self.assertEqual(self.product.description, "Blazer Alfaiataria Gold")
        self.assertEqual(self.product.cost_price, Decimal("120.00"))
        self.assertEqual(self.product.sale_price, Decimal("299.90"))
        self.assertEqual(self.product.stock_quantity, 5)

        # Setter verification
        self.product.name = "Novo Blazer"
        self.product.cost_price = Decimal("130.00")
        self.assertEqual(self.product.descricao, "Novo Blazer")
        self.assertEqual(self.product.preco_custo, Decimal("130.00"))

    def test_stock_transaction_creation(self):
        """Test StockTransaction creation and relation to Product."""
        tx = StockTransaction.objects.create(
            product=self.product,
            transaction_type='IN',
            quantity=10,
            unit_price=Decimal("120.00"),
            notes="Recebimento de nova remessa"
        )
        self.assertEqual(tx.product.cod_unico, "FER-101")
        self.assertEqual(tx.quantity, 10)

    def test_product_list_view_rendering(self):
        """Test product list view returns status 200 and includes HTMX totalizer table."""
        url = reverse('inventory:product_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blazer Alfaiataria Gold")
        self.assertContains(response, "FER-101")
        self.assertContains(response, "fersie-table")
        self.assertContains(response, "fersie-totalizer-row")

    def test_product_list_search_filter(self):
        """Test product list view search filter by query string."""
        url = reverse('inventory:product_list')
        response = self.client.get(url, {'q': 'Blazer'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blazer Alfaiataria Gold")

        response_empty = self.client.get(url, {'q': 'Inexistente999'})
        self.assertEqual(response_empty.status_code, 200)
        self.assertNotContains(response_empty, "Blazer Alfaiataria Gold")

    def test_product_list_sorting_and_pagination(self):
        """Test product list view sorting and pagination."""
        for i in range(15):
            Product.objects.create(
                cod_unico=f"FER-20{i}",
                descricao=f"Camisa Linho {i}",
                preco_custo=Decimal("50.00"),
                preco_venda=Decimal("150.00"),
                quantidade=10
            )

        url = reverse('inventory:product_list')
        response_page1 = self.client.get(url, {'page': 1, 'per_page': 10, 'sort': 'descricao'})
        self.assertEqual(response_page1.status_code, 200)
        self.assertContains(response_page1, "fersie-pagination")

        response_page2 = self.client.get(url, {'page': 2, 'per_page': 10, 'sort': 'descricao'})
        self.assertEqual(response_page2.status_code, 200)

    def test_product_bulk_actions(self):
        """Test product bulk actions endpoint."""
        p1 = Product.objects.create(cod_unico="B-1", descricao="Item 1", preco_venda=10, quantidade=5)
        p2 = Product.objects.create(cod_unico="B-2", descricao="Item 2", preco_venda=20, quantidade=0)

        url = reverse('inventory:product_bulk_action')
        response = self.client.post(url, {'selected_ids': [p1.id, p2.id], 'bulk_action': 'zero_stock'})
        self.assertEqual(response.status_code, 200)
        p1.refresh_from_db()
        self.assertEqual(p1.quantidade, 0)

        response_del = self.client.post(url, {'selected_ids': [p1.id], 'bulk_action': 'delete'})
        self.assertEqual(response_del.status_code, 200)
        self.assertFalse(Product.objects.filter(id=p1.id).exists())

