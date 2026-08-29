from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.utils import timezone
from inventory.models import Product, Supplier as InventorySupplier

class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Nome / Razão Social")
    cnpj_cpf = models.CharField(max_length=30, blank=True, verbose_name="CNPJ / CPF")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Telefone")
    email = models.EmailField(max_length=100, blank=True, verbose_name="E-mail")
    notes = models.TextField(blank=True, verbose_name="Observações")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"

    def __str__(self):
        return self.name

class Purchase(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Pago'),
        ('pending', 'Pendente'),
    ]

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchases', verbose_name="Fornecedor")
    invoice_number = models.CharField(max_length=50, blank=True, verbose_name="Número da Nota Fiscal")
    date = models.DateField(default=timezone.now, verbose_name="Data da Compra")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Valor Total")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    notes = models.TextField(blank=True, verbose_name="Observações")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"

    def __str__(self):
        return f"Compra #{self.id} - {self.supplier.name} (R$ {self.total_amount})"

class PurchaseItem(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchase_items')
    quantity = models.IntegerField(default=1, verbose_name="Quantidade")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Custo Unitário")
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Custo Total")

    def save(self, *args, **kwargs):
        self.total_cost = Decimal(str(self.unit_cost)) * Decimal(str(self.quantity))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.descricao} ({self.quantity}x R$ {self.unit_cost})"

class Sale(models.Model):
    SALE_TYPE_CHOICES = [
        ('balcao', 'Balcão / Loja Física'),
        ('online', 'Venda Online / WhatsApp'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('dinheiro', 'Dinheiro'),
        ('pix', 'PIX'),
        ('cartao_credito', 'Cartão de Crédito'),
        ('cartao_debito', 'Cartão de Débito'),
    ]

    STATUS_CHOICES = [
        ('completed', 'Concluída'),
        ('cancelled', 'Cancelada'),
    ]

    sale_code = models.CharField(max_length=50, unique=True, verbose_name="Código da Venda")
    customer_name = models.CharField(max_length=150, blank=True, verbose_name="Nome do Cliente")
    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='balcao', verbose_name="Tipo de Venda")
    date = models.DateField(default=timezone.now, verbose_name="Data da Venda")
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, default='dinheiro', verbose_name="Forma de Pagamento")
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Valor Bruto")
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Desconto")
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Valor Líquido")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True)

    # Legacy compatibility fields for single-product sale instances
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Venda"
        verbose_name_plural = "Vendas"

    @property
    def total_price(self):
        return self.net_amount if self.net_amount > 0 else (self.gross_amount - Decimal(str(self.discount or 0)))

    @total_price.setter
    def total_price(self, val):
        self.net_amount = val

    @property
    def channel(self):
        return self.sale_type

    @channel.setter
    def channel(self, val):
        if val in ['STORE', 'balcao']:
            self.sale_type = 'balcao'
        elif val in ['ONLINE', 'online']:
            self.sale_type = 'online'

    def save(self, *args, **kwargs):
        pm_map = {
            'CREDIT': 'cartao_credito',
            'DEBIT': 'cartao_debito',
            'CASH': 'dinheiro',
            'PIX': 'pix',
        }
        if self.payment_method in pm_map:
            self.payment_method = pm_map[self.payment_method]

        if not self.sale_code:
            import uuid
            self.sale_code = f"VENDA-{uuid.uuid4().hex[:8].upper()}"

        if self.gross_amount == 0 and self.unit_price > 0 and self.quantity > 0:
            self.gross_amount = Decimal(str(self.unit_price)) * Decimal(str(self.quantity))

        if not self.net_amount or self.net_amount == 0:
            self.net_amount = Decimal(str(self.gross_amount)) - Decimal(str(self.discount or 0))

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Venda #{self.sale_code} - R$ {self.net_amount}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sale_items')
    quantity = models.IntegerField(default=1, verbose_name="Quantidade")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço Unitário")
    total_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Preço Total")

    def save(self, *args, **kwargs):
        self.total_price = Decimal(str(self.unit_price)) * Decimal(str(self.quantity))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.descricao} ({self.quantity}x R$ {self.unit_price})"

class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('operacional', 'Operacional'),
        ('aluguel', 'Aluguel'),
        ('fornecedores', 'Fornecedores'),
        ('marketing', 'Marketing'),
        ('impostos', 'Impostos'),
        ('outros', 'Outros'),
    ]

    STATUS_CHOICES = [
        ('pago', 'Pago'),
        ('pendente', 'Pendente'),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='operacional', verbose_name="Categoria")
    description = models.CharField(max_length=255, verbose_name="Descrição da Despesa")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor (R$)")
    due_date = models.DateField(verbose_name="Data de Vencimento")
    payment_date = models.DateField(null=True, blank=True, verbose_name="Data de Pagamento")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name="Status")
    receipt_notes = models.TextField(blank=True, verbose_name="Observações / Recibo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Despesa"
        verbose_name_plural = "Despesas"

    @property
    def is_paid(self):
        return self.status == 'pago'

    @is_paid.setter
    def is_paid(self, value):
        if isinstance(value, bool):
            self.status = 'pago' if value else 'pendente'
        elif value:
            self.status = 'pago'

    def __str__(self):
        return f"Despesa: {self.description} (R$ {self.amount})"

class AccountsReceivable(models.Model):
    STATUS_CHOICES = [
        ('pago', 'Pago'),
        ('pendente', 'Pendente'),
    ]

    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='receivables', verbose_name="Venda Originária")
    customer_name = models.CharField(max_length=150, blank=True, verbose_name="Nome do Cliente")
    description = models.CharField(max_length=255, blank=True, verbose_name="Descrição")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Valor Total (R$)")
    due_date = models.DateField(null=True, blank=True, verbose_name="Data de Vencimento")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name="Status")
    payment_method = models.CharField(max_length=30, blank=True, verbose_name="Forma de Pagamento")
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Valor Recebido (R$)")
    received_date = models.DateField(null=True, blank=True, verbose_name="Data de Recebimento")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Conta a Receber"
        verbose_name_plural = "Contas a Receber"

    def __str__(self):
        return f"Recebível: {self.customer_name or 'Cliente'} (R$ {self.total_amount})"

class CardReconciliation(models.Model):
    CARD_BRAND_CHOICES = [
        ('visa', 'Visa'),
        ('mastercard', 'Mastercard'),
        ('elo', 'Elo'),
        ('outras', 'Outras'),
    ]

    TRANSACTION_TYPE_CHOICES = [
        ('debito', 'Débito'),
        ('credito_avista', 'Crédito à Vista'),
        ('credito_parcelado', 'Crédito Parcelado'),
    ]

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('conciliado', 'Conciliado'),
        ('divergente', 'Divergente'),
    ]

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='card_reconciliations', verbose_name="Venda")
    card_brand = models.CharField(max_length=30, choices=CARD_BRAND_CHOICES, default='visa', verbose_name="Bandeira do Cartão")
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPE_CHOICES, default='debito', verbose_name="Tipo de Transação")
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Valor Bruto (R$)")
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, verbose_name="Taxa MDR (%)")
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Valor da Taxa (R$)")
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Valor Líquido (R$)")
    expected_settlement_date = models.DateField(null=True, blank=True, verbose_name="Data Prevista de Repasse")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name="Status de Conciliação")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Conciliação de Cartão"
        verbose_name_plural = "Conciliações de Cartões"

    @property
    def card_operator(self):
        return self.get_card_brand_display()

    @property
    def reconciled(self):
        return self.status == 'conciliado'

    @reconciled.setter
    def reconciled(self, value):
        self.status = 'conciliado' if value else 'pendente'

    @property
    def payout_date(self):
        return self.expected_settlement_date

    @payout_date.setter
    def payout_date(self, value):
        self.expected_settlement_date = value

    def save(self, *args, **kwargs):
        if self.gross_amount > 0 and self.fee_percentage >= 0:
            if not self.fee_amount or self.fee_amount == 0:
                self.fee_amount = round(Decimal(str(self.gross_amount)) * (Decimal(str(self.fee_percentage)) / Decimal('100.0')), 2)
            if not self.net_amount or self.net_amount == 0:
                self.net_amount = Decimal(str(self.gross_amount)) - Decimal(str(self.fee_amount))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Conciliação Venda #{self.sale.sale_code} ({self.get_card_brand_display()} - R$ {self.net_amount})"
