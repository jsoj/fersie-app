import os
import re
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from inventory.models import Product, Supplier, Category

DEFAULT_EXCEL_PATH = "/home/jsoj/fersie/Planilha Mercadoria_JUNIOR_v2.xlsx"

def clean_str(val):
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null"):
        return ""
    return s

def parse_price(val):
    if val is None:
        return Decimal("0.00")
    s = str(val).strip().replace("R$", "").replace("r$", "").replace(" ", "")
    if not s or s.lower() in ("nan", "none", "null"):
        return Decimal("0.00")
    # Convert Brazilian float string like "199,90" to "199.90"
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        d = Decimal(s)
        return round(d, 2)
    except (ValueError, InvalidOperation):
        return Decimal("0.00")

def parse_qty(val):
    if val is None:
        return 1
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return 1
    try:
        # Handle floats like 10.0 in Excel
        f = float(s)
        return int(f)
    except ValueError:
        return 1

class Command(BaseCommand):
    help = 'Ingests Excel merchandise file (Planilha Mercadoria_JUNIOR_v2.xlsx) idempotently into inventory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default=DEFAULT_EXCEL_PATH,
            help='Path to the Excel file to import'
        )

    def load_excel_rows(self, filepath):
        if not os.path.exists(filepath):
            raise CommandError(f"Spreadsheet file not found at path: {filepath}")

        # Method 1: Try openpyxl
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filepath, data_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            if rows:
                headers = [clean_str(c).lower() for c in rows[0]]
                data_rows = []
                for r in rows[1:]:
                    if any(c is not None for c in r):
                        row_dict = {}
                        for idx, h in enumerate(headers):
                            if h:
                                row_dict[h] = r[idx] if idx < len(r) else None
                        data_rows.append(row_dict)
                return data_rows
        except ImportError:
            pass

        # Method 2: Try pandas
        try:
            import pandas as pd
            df = pd.read_excel(filepath)
            df.columns = [clean_str(c).lower() for c in df.columns]
            data_rows = df.to_dict(orient='records')
            return data_rows
        except ImportError:
            pass

        # Method 3: Direct XML parsing via zipfile
        with zipfile.ZipFile(filepath, 'r') as z:
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                ss_tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for si in ss_tree.findall('.//main:si', ns) or ss_tree.findall('.//si'):
                    text = "".join([t.text or "" for t in (si.findall('.//main:t', ns) or si.findall('.//t'))])
                    shared_strings.append(text)

            sheet_name = 'xl/worksheets/sheet1.xml'
            if sheet_name not in z.namelist():
                sheets = [f for f in z.namelist() if f.startswith('xl/worksheets/sheet')]
                sheet_name = sheets[0] if sheets else None

            if not sheet_name:
                return []

            sheet_tree = ET.fromstring(z.read(sheet_name))
            ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

            parsed_rows = []
            row_elements = sheet_tree.findall('.//main:row', ns) or sheet_tree.findall('.//row')
            for r_elem in row_elements:
                cells = r_elem.findall('./main:c', ns) or r_elem.findall('./c')
                row_data = []
                for cell in cells:
                    t_attr = cell.attrib.get('t', '')
                    v_elem = cell.find('./main:v', ns) if ns else cell.find('./v')
                    if v_elem is not None and v_elem.text:
                        val = v_elem.text
                        if t_attr == 's' and int(val) < len(shared_strings):
                            val = shared_strings[int(val)]
                        elif t_attr != 's':
                            try:
                                val = float(val) if '.' in val else int(val)
                            except ValueError:
                                pass
                        row_data.append(val)
                    else:
                        row_data.append(None)
                if any(v is not None for v in row_data):
                    parsed_rows.append(row_data)

            if not parsed_rows:
                return []

            headers = [clean_str(h).lower() for h in parsed_rows[0]]
            data_rows = []
            for r in parsed_rows[1:]:
                row_dict = {}
                for idx, h in enumerate(headers):
                    if h:
                        row_dict[h] = r[idx] if idx < len(r) else None
                data_rows.append(row_dict)

            return data_rows

    def extract_field(self, row, aliases, default=""):
        for alias in aliases:
            if alias in row and row[alias] is not None:
                val = clean_str(row[alias])
                if val:
                    return val
        return default

    def handle(self, *args, **options):
        filepath = options.get('file', DEFAULT_EXCEL_PATH)
        self.stdout.write(f"Starting Excel merchandise ingestion from: {filepath}")

        rows = self.load_excel_rows(filepath)
        if not rows:
            self.stdout.write(self.style.WARNING("No data rows found in spreadsheet."))
            return

        created_count = 0
        updated_count = 0
        skipped_count = 0

        # Column Aliases
        code_aliases = ["cod_unico", "código", "codigo", "referência", "referencia", "cód", "cod", "barras", "code", "barcode"]
        desc_aliases = ["descrição", "descricao", "produto", "nome", "item", "description", "name"]
        cat_aliases = ["categoria", "grupo", "category"]
        cost_aliases = ["preço_custo", "preco_custo", "custo", "valor compra", "preço custo", "preco custo", "cost_price"]
        sale_aliases = ["preço_venda", "preco_venda", "venda", "preço", "preco", "valor venda", "preço venda", "preco venda", "sale_price"]
        qty_aliases = ["estoque", "qtd", "quantidade", "qtd_estoque", "stock", "qty"]
        color_aliases = ["cor", "color"]
        size_aliases = ["tamanho", "size"]
        supplier_aliases = ["fornecedor", "supplier"]

        for idx, row in enumerate(rows):
            code_val = self.extract_field(row, code_aliases)
            if not code_val:
                # Generate fallback code if missing
                code_val = f"FER-AUTO-{idx+1:04d}"

            desc_val = self.extract_field(row, desc_aliases, default=f"Produto {code_val}")
            cat_name = self.extract_field(row, cat_aliases, default="Alfaiataria")
            color_val = self.extract_field(row, color_aliases)
            size_val = self.extract_field(row, size_aliases)
            supplier_name = self.extract_field(row, supplier_aliases)

            # Raw values for price and quantity
            raw_cost = None
            for alias in cost_aliases:
                if alias in row and row[alias] is not None:
                    raw_cost = row[alias]
                    break
            cost_val = parse_price(raw_cost)

            raw_sale = None
            for alias in sale_aliases:
                if alias in row and row[alias] is not None:
                    raw_sale = row[alias]
                    break
            sale_val = parse_price(raw_sale)

            raw_qty = None
            for alias in qty_aliases:
                if alias in row and row[alias] is not None:
                    raw_qty = row[alias]
                    break
            qty_val = parse_qty(raw_qty)

            # Category & Supplier lookup/creation
            category_obj = None
            if cat_name:
                category_obj, _ = Category.objects.get_or_create(
                    name=cat_name,
                    defaults={"description": f"Categoria {cat_name}"}
                )

            supplier_obj = None
            if supplier_name:
                supplier_obj, _ = Supplier.objects.get_or_create(
                    name=supplier_name
                )

            # Idempotent update_or_create
            product, created = Product.objects.update_or_create(
                cod_unico=code_val,
                defaults={
                    "descricao": desc_val,
                    "cor": color_val,
                    "tamanho": size_val,
                    "preco_custo": cost_val,
                    "preco_venda": sale_val,
                    "quantidade": qty_val,
                    "categoria": cat_name,
                    "category_obj": category_obj,
                    "fornecedor": supplier_obj,
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully processed Excel merchandise ingestion!\n"
                f"Created: {created_count}\n"
                f"Updated: {updated_count}\n"
                f"Skipped: {skipped_count}\n"
                f"Total Products in DB: {Product.objects.count()}"
            )
        )
