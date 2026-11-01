from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='exibir_no_site',
            field=models.BooleanField(default=False, verbose_name='Exibir no Site (fersie.com)'),
        ),
        migrations.AddField(
            model_name='product',
            name='destaque_vitrine',
            field=models.BooleanField(default=False, verbose_name='Destaque na Home'),
        ),
    ]
