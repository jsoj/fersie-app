from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Categoria")
    description = models.TextField(blank=True, verbose_name="Descrição")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"

    def __str__(self):
        return self.name

class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Fornecedor")
    contact_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"

    def __str__(self):
        return self.name

class Product(models.Model):
    cod_unico = models.CharField(max_length=50, unique=True, verbose_name="Código Único")
    descricao = models.CharField(max_length=255, verbose_name="Descrição")
    cor = models.CharField(max_length=50, blank=True, verbose_name="Cor")
    tamanho = models.CharField(max_length=20, blank=True, verbose_name="Tamanho")
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Preço de Custo")
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Preço de Venda")
    fornecedor = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Fornecedor")
    quantidade = models.IntegerField(default=1, verbose_name="Quantidade em Estoque")
    categoria = models.CharField(max_length=50, default="Alfaiataria", verbose_name="Categoria")
    category_obj = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products", verbose_name="Objeto Categoria")
    exibir_no_site = models.BooleanField(default=False, verbose_name="Exibir no Site (fersie.com)")
    destaque_vitrine = models.BooleanField(default=False, verbose_name="Destaque na Home")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

    def __str__(self):
        return f"[{self.cod_unico}] {self.descricao} - {self.cor}/{self.tamanho}"

    # Properties to support English schema contract compatibility
    @property
    def code(self):
        return self.cod_unico

    @code.setter
    def code(self, val):
        self.cod_unico = val

    @property
    def barcode(self):
        return self.cod_unico

    @barcode.setter
    def barcode(self, val):
        self.cod_unico = val

    @property
    def name(self):
        return self.descricao

    @name.setter
    def name(self, val):
        self.descricao = val

    @property
    def description(self):
        return self.descricao

    @description.setter
    def description(self, val):
        self.descricao = val

    @property
    def cost_price(self):
        return self.preco_custo

    @cost_price.setter
    def cost_price(self, val):
        self.preco_custo = val

    @property
    def sale_price(self):
        return self.preco_venda

    @sale_price.setter
    def sale_price(self, val):
        self.preco_venda = val

    @property
    def stock_quantity(self):
        return self.quantidade

    @stock_quantity.setter
    def stock_quantity(self, val):
        self.quantidade = val

class StockTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('IN', 'Entrada'),
        ('OUT', 'Saída'),
        ('ADJUSTMENT', 'Ajuste'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='IN')
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, verbose_name="Observações")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Movimentação de Estoque"
        verbose_name_plural = "Movimentações de Estoque"

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.product.cod_unico} (Qtd: {self.quantity})"
