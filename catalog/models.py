from django.db import models
from inventory.models import Product

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    is_primary = models.BooleanField(default=False)
    alt_text = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Foto de {self.product.descricao}"

class BarcodeLabelTemplate(models.Model):
    PRINTER_TYPE_CHOICES = [
        ('ELGIN_L42PRO', 'Elgin L42PRO FULL (TSPL/EPL)'),
        ('ZEBRA_ZPL', 'Zebra ZPL II'),
        ('GENERIC_PDF', 'PDF Genérico 50x30mm'),
    ]

    name = models.CharField(max_length=100, default="Etiqueta Padrão Elgin 50x30mm")
    printer_type = models.CharField(max_length=30, choices=PRINTER_TYPE_CHOICES, default='ELGIN_L42PRO')
    width_mm = models.IntegerField(default=50)
    height_mm = models.IntegerField(default=30)
    tspl_template = models.TextField(blank=True, help_text="Template TSPL/EPL para Elgin L42PRO FULL")

    def __str__(self):
        return f"{self.name} ({self.get_printer_type_display()})"
