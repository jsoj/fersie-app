from django.test import TestCase, Client
from django.urls import reverse
from inventory.models import Product, Supplier, Category
from catalog.models import BarcodeLabelTemplate, ProductImage
from catalog.utils import (
    normalize_barcode,
    generate_elgin_tspl_label,
    generate_elgin_epl_label,
    generate_elgin_zpl_label,
    generate_barcode_svg,
    generate_qr_code_svg,
)


class CatalogModelsTest(TestCase):
    def test_barcode_label_template_defaults(self):
        template = BarcodeLabelTemplate.objects.create()
        self.assertEqual(template.width_mm, 50)
        self.assertEqual(template.height_mm, 30)
        self.assertEqual(template.printer_type, 'ELGIN_L42PRO')

    def test_product_image_creation(self):
        supplier = Supplier.objects.create(name="Supplier Test")
        product = Product.objects.create(
            cod_unico="TEST-001",
            descricao="Vestido Silk",
            cor="Rosa",
            tamanho="M",
            preco_custo=50.00,
            preco_venda=120.00,
            quantidade=10,
            fornecedor=supplier
        )
        img = ProductImage.objects.create(
            product=product,
            image="products/test.jpg",
            is_primary=True,
            alt_text="Foto do Vestido Silk"
        )
        self.assertEqual(img.product, product)
        self.assertTrue(img.is_primary)
        self.assertEqual(img.alt_text, "Foto do Vestido Silk")
        self.assertIn("Vestido Silk", str(img))


class CatalogUtilsTest(TestCase):
    def test_normalize_barcode(self):
        self.assertEqual(normalize_barcode(" 7891234567890 \r\n"), "7891234567890")
        self.assertEqual(normalize_barcode(" FER-001 "), "FER-001")
        self.assertEqual(normalize_barcode(None), "")

    def test_generate_elgin_tspl_label(self):
        tspl_output = generate_elgin_tspl_label("FER-999", "Blouse Silk", 189.90)
        self.assertIn("SIZE 50 mm, 30 mm", tspl_output)
        self.assertIn('BARCODE 20,60,"128"', tspl_output)
        self.assertIn("FER-999", tspl_output)
        self.assertIn("R$ 189,90", tspl_output)
        self.assertIn("PRINT 1,1", tspl_output)

    def test_generate_elgin_epl_and_zpl(self):
        epl = generate_elgin_epl_label("FER-100", "Calça Alfaiataria", 259.00)
        self.assertIn('A20,20,0,3,1,1,N,"FERSIE - Calça Alfaiataria"', epl)
        self.assertIn('B20,60,0,1,2,2,60,B,"FER-100"', epl)

        zpl = generate_elgin_zpl_label("FER-100", "Calça Alfaiataria", 259.00)
        self.assertIn("^XA", zpl)
        self.assertIn("^FDFERSIE - Calça Alfaiataria^FS", zpl)
        self.assertIn("^FDFER-100^FS", zpl)

    def test_generate_barcode_and_qr_svg(self):
        barcode_svg = generate_barcode_svg("FER-001", width=220, height=70)
        self.assertIn("<svg", barcode_svg)
        self.assertIn("FER-001", barcode_svg)

        qr_svg = generate_qr_code_svg("FER-001", size=120)
        self.assertIn("<svg", qr_svg)

    def test_code128_patterns_integrity(self):
        from catalog.utils import CODE128_PATTERNS
        self.assertEqual(len(CODE128_PATTERNS), 103)
        for idx, pattern in enumerate(CODE128_PATTERNS):
            self.assertEqual(len(pattern), 6, f"Pattern at index {idx} must have length 6")
            modules_sum = sum(int(d) for d in pattern)
            self.assertEqual(modules_sum, 11, f"Pattern at index {idx} ({pattern}) must sum to 11 modules")
        self.assertEqual(CODE128_PATTERNS[49], "314111")
        self.assertEqual(CODE128_PATTERNS[56], "311141")
        self.assertNotEqual(CODE128_PATTERNS[49], CODE128_PATTERNS[56])

    def test_barcode_checksum_index_above_95(self):
        from catalog.utils import generate_barcode_svg, CODE128_PATTERNS
        svg_95 = generate_barcode_svg("~")
        self.assertIn("<svg", svg_95)
        self.assertIn("~", svg_95)
        self.assertEqual(sum(int(d) for d in CODE128_PATTERNS[95]), 11)

        svg_97 = generate_barcode_svg("~!")
        self.assertIn("<svg", svg_97)

    def test_thermal_label_quote_escaping(self):
        code = 'FER-"001"'
        desc = 'Blusa "Seda"'
        price = 150.00

        tspl = generate_elgin_tspl_label(code, desc, price)
        self.assertIn('FERSIE - Blusa \\"Seda\\"', tspl)
        self.assertIn('BARCODE 20,60,"128",60,1,0,2,2,"FER-\\"001\\""', tspl)

        epl = generate_elgin_epl_label(code, desc, price)
        self.assertIn('FERSIE - Blusa \\"Seda\\"', epl)
        self.assertIn('B20,60,0,1,2,2,60,B,"FER-\\"001\\""', epl)

        zpl = generate_elgin_zpl_label(code, desc, price)
        self.assertIn('FERSIE - Blusa \\"Seda\\"', zpl)
        self.assertIn('FER-\\"001\\"', zpl)


class CatalogViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.cat1 = Category.objects.create(name="Alfaiataria")
        self.cat2 = Category.objects.create(name="Bijuterias")

        self.p1 = Product.objects.create(
            cod_unico="FER-001",
            descricao="Blazer Alfaiataria",
            cor="Preto",
            tamanho="M",
            preco_custo=100.00,
            preco_venda=250.00,
            quantidade=5,
            categoria="Alfaiataria",
            category_obj=self.cat1
        )
        self.p2 = Product.objects.create(
            cod_unico="FER-002",
            descricao="Brinco Dourado",
            cor="Dourado",
            tamanho="U",
            preco_custo=15.00,
            preco_venda=45.00,
            quantidade=2,
            categoria="Bijuterias",
            category_obj=self.cat2
        )
        self.p3 = Product.objects.create(
            cod_unico="FER-003",
            descricao="Regata Seda",
            cor="Branco",
            tamanho="P",
            preco_custo=40.00,
            preco_venda=110.00,
            quantidade=0,
            categoria="Alfaiataria",
            category_obj=self.cat1
        )

    def test_visual_catalog_view_renders(self):
        response = self.client.get(reverse('catalog:visual_catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Catálogo Visual")
        self.assertContains(response, "FER-001")
        self.assertContains(response, "Blazer Alfaiataria")

    def test_visual_catalog_filtering_by_category(self):
        response = self.client.get(reverse('catalog:visual_catalog') + '?category=Bijuterias')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FER-002")
        self.assertNotContains(response, "FER-001")

    def test_visual_catalog_filtering_by_search_query(self):
        response = self.client.get(reverse('catalog:visual_catalog') + '?q=Blazer')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FER-001")
        self.assertNotContains(response, "FER-002")

    def test_visual_catalog_filtering_by_stock_status(self):
        # in_stock (>3) -> p1 (5)
        response_in = self.client.get(reverse('catalog:visual_catalog') + '?stock=in_stock')
        self.assertContains(response_in, "FER-001")
        self.assertNotContains(response_in, "FER-002")

        # low_stock (1-3) -> p2 (2)
        response_low = self.client.get(reverse('catalog:visual_catalog') + '?stock=low_stock')
        self.assertContains(response_low, "FER-002")
        self.assertNotContains(response_low, "FER-001")

        # out_of_stock (<=0) -> p3 (0)
        response_out = self.client.get(reverse('catalog:visual_catalog') + '?stock=out_of_stock')
        self.assertContains(response_out, "FER-003")

    def test_visual_catalog_htmx_partial_response(self):
        response = self.client.get(reverse('catalog:visual_catalog'), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FER-001")
        self.assertNotContains(response, "<!DOCTYPE html>")

    def test_quick_view_modal(self):
        response = self.client.get(reverse('catalog:quick_view_modal', kwargs={'code_or_id': self.p1.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Detalhes do Produto — FER-001")
        self.assertContains(response, "SIZE 50 mm, 30 mm")

    def test_scanner_view(self):
        response = self.client.get(reverse('catalog:scanner'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Leitor de Código de Barras")

    def test_scan_lookup_existing_product(self):
        response = self.client.get(reverse('catalog:scan_lookup', kwargs={'code_unico': 'FER-001'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Produto Encontrado")
        self.assertContains(response, "Blazer Alfaiataria")

    def test_scan_lookup_non_existing_product(self):
        response = self.client.get(reverse('catalog:scan_lookup', kwargs={'code_unico': 'INVALID-999'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Código não encontrado")
        self.assertContains(response, "INVALID-999")

    def test_label_generator_and_preview_views(self):
        gen_resp = self.client.get(reverse('catalog:label_generator'))
        self.assertEqual(gen_resp.status_code, 200)
        self.assertContains(gen_resp, "Impressão de Etiquetas — Elgin L42PRO FULL")

        prev_resp = self.client.get(reverse('catalog:label_preview') + f'?code={self.p1.cod_unico}&qty=2')
        self.assertEqual(prev_resp.status_code, 200)
        self.assertContains(prev_resp, "SIZE 50 mm, 30 mm")
        self.assertContains(prev_resp, "FER-001")

    def test_label_print_view(self):
        html_resp = self.client.get(reverse('catalog:label_print') + f'?code={self.p1.cod_unico}&qty=1&mode=html')
        self.assertEqual(html_resp.status_code, 200)
        self.assertContains(html_resp, "FERSIE")
        self.assertContains(html_resp, "FER-001")

        tspl_resp = self.client.get(reverse('catalog:label_print') + f'?code={self.p1.cod_unico}&qty=1&mode=tspl')
        self.assertEqual(tspl_resp.status_code, 200)
        self.assertEqual(tspl_resp['Content-Type'], 'text/plain')
        self.assertContains(tspl_resp, "SIZE 50 mm, 30 mm")
        self.assertContains(tspl_resp, "FER-001")
