from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True, verbose_name='Nome / Razão Social')),
                ('cnpj_cpf', models.CharField(blank=True, max_length=30, verbose_name='CNPJ / CPF')),
                ('phone', models.CharField(blank=True, max_length=30, verbose_name='Telefone')),
                ('email', models.EmailField(blank=True, max_length=100, verbose_name='E-mail')),
                ('notes', models.TextField(blank=True, verbose_name='Observações')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Fornecedor',
                'verbose_name_plural': 'Fornecedores',
            },
        ),
        migrations.CreateModel(
            name='Purchase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_number', models.CharField(blank=True, max_length=50, verbose_name='Número da Nota Fiscal')),
                ('date', models.DateField(default=django.utils.timezone.now, verbose_name='Data da Compra')),
                ('total_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name='Valor Total')),
                ('status', models.CharField(choices=[('paid', 'Pago'), ('pending', 'Pendente')], default='pending', max_length=20, verbose_name='Status')),
                ('notes', models.TextField(blank=True, verbose_name='Observações')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('supplier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='purchases', to='financial.supplier', verbose_name='Fornecedor')),
            ],
            options={
                'verbose_name': 'Compra',
                'verbose_name_plural': 'Compras',
            },
        ),
        migrations.CreateModel(
            name='PurchaseItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=1, verbose_name='Quantidade')),
                ('unit_cost', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Custo Unitário')),
                ('total_cost', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Custo Total')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='purchase_items', to='inventory.product')),
                ('purchase', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='financial.purchase')),
            ],
        ),
        migrations.CreateModel(
            name='Sale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sale_code', models.CharField(max_length=50, unique=True, verbose_name='Código da Venda')),
                ('customer_name', models.CharField(blank=True, max_length=150, verbose_name='Nome do Cliente')),
                ('sale_type', models.CharField(choices=[('balcao', 'Balcão / Loja Física'), ('online', 'Venda Online / WhatsApp')], default='balcao', max_length=20, verbose_name='Tipo de Venda')),
                ('date', models.DateField(default=django.utils.timezone.now, verbose_name='Data da Venda')),
                ('payment_method', models.CharField(choices=[('dinheiro', 'Dinheiro'), ('pix', 'PIX'), ('cartao_credito', 'Cartão de Crédito'), ('cartao_debito', 'Cartão de Débito')], default='dinheiro', max_length=30, verbose_name='Forma de Pagamento')),
                ('gross_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name='Valor Bruto')),
                ('discount', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name='Desconto')),
                ('net_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name='Valor Líquido')),
                ('status', models.CharField(choices=[('completed', 'Concluída'), ('cancelled', 'Cancelada')], default='completed', max_length=20, verbose_name='Status')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('quantity', models.IntegerField(default=1)),
                ('unit_price', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sales', to='inventory.product')),
            ],
            options={
                'verbose_name': 'Venda',
                'verbose_name_plural': 'Vendas',
            },
        ),
        migrations.CreateModel(
            name='SaleItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.IntegerField(default=1, verbose_name='Quantidade')),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Preço Unitário')),
                ('total_price', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Preço Total')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sale_items', to='inventory.product')),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='financial.sale')),
            ],
        ),
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('operacional', 'Operacional'), ('aluguel', 'Aluguel'), ('fornecedores', 'Fornecedores'), ('marketing', 'Marketing'), ('impostos', 'Impostos'), ('outros', 'Outros')], default='operacional', max_length=50, verbose_name='Categoria')),
                ('description', models.CharField(max_length=255, verbose_name='Descrição da Despesa')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Valor (R$)')),
                ('due_date', models.DateField(verbose_name='Data de Vencimento')),
                ('payment_date', models.DateField(blank=True, null=True, verbose_name='Data de Pagamento')),
                ('status', models.CharField(choices=[('pago', 'Pago'), ('pendente', 'Pendente')], default='pendente', max_length=20, verbose_name='Status')),
                ('receipt_notes', models.TextField(blank=True, verbose_name='Observações / Recibo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Despesa',
                'verbose_name_plural': 'Despesas',
            },
        ),
        migrations.CreateModel(
            name='AccountsReceivable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('customer_name', models.CharField(blank=True, max_length=150, verbose_name='Nome do Cliente')),
                ('description', models.CharField(blank=True, max_length=255, verbose_name='Descrição')),
                ('total_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name='Valor Total (R$)')),
                ('due_date', models.DateField(blank=True, null=True, verbose_name='Data de Vencimento')),
                ('status', models.CharField(choices=[('pago', 'Pago'), ('pendente', 'Pendente')], default='pendente', max_length=20, verbose_name='Status')),
                ('payment_method', models.CharField(blank=True, max_length=30, verbose_name='Forma de Pagamento')),
                ('received_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name='Valor Recebido (R$)')),
                ('received_date', models.DateField(blank=True, null=True, verbose_name='Data de Recebimento')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sale', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receivables', to='financial.sale', verbose_name='Venda Originária')),
            ],
            options={
                'verbose_name': 'Conta a Receber',
                'verbose_name_plural': 'Contas a Receber',
            },
        ),
        migrations.CreateModel(
            name='CardReconciliation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('card_brand', models.CharField(choices=[('visa', 'Visa'), ('mastercard', 'Mastercard'), ('elo', 'Elo'), ('outras', 'Outras')], default='visa', max_length=30, verbose_name='Bandeira do Cartão')),
                ('transaction_type', models.CharField(choices=[('debito', 'Débito'), ('credito_avista', 'Crédito à Vista'), ('credito_parcelado', 'Crédito Parcelado')], default='debito', max_length=30, verbose_name='Tipo de Transação')),
                ('gross_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name='Valor Bruto (R$)')),
                ('fee_percentage', models.DecimalField(decimal_places=2, default=0.0, max_digits=5, verbose_name='Taxa MDR (%)')),
                ('fee_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name='Valor da Taxa (R$)')),
                ('net_amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=12, verbose_name='Valor Líquido (R$)')),
                ('expected_settlement_date', models.DateField(blank=True, null=True, verbose_name='Data Prevista de Repasse')),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('conciliado', 'Conciliado'), ('divergente', 'Divergente')], default='pendente', max_length=20, verbose_name='Status de Conciliação')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='card_reconciliations', to='financial.sale', verbose_name='Venda')),
            ],
            options={
                'verbose_name': 'Conciliação de Cartão',
                'verbose_name_plural': 'Conciliações de Cartões',
            },
        ),
    ]
