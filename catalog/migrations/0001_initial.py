from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BarcodeLabelTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='Etiqueta Padrão Elgin 50x30mm', max_length=100)),
                ('printer_type', models.CharField(choices=[('ELGIN_L42PRO', 'Elgin L42PRO FULL (TSPL/EPL)'), ('ZEBRA_ZPL', 'Zebra ZPL II'), ('GENERIC_PDF', 'PDF Genérico 50x30mm')], default='ELGIN_L42PRO', max_length=30)),
                ('width_mm', models.IntegerField(default=50)),
                ('height_mm', models.IntegerField(default=30)),
                ('tspl_template', models.TextField(blank=True, help_text='Template TSPL/EPL para Elgin L42PRO FULL')),
            ],
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='products/')),
                ('is_primary', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='inventory.product')),
            ],
        ),
    ]
