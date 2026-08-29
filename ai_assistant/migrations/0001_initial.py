from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AIAssistantConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_key', models.CharField(blank=True, default='', help_text='Opcional. Se em branco, utiliza a variável de ambiente GEMINI_API_KEY', max_length=255, verbose_name='Chave API (Gemini)')),
                ('model_name', models.CharField(default='gemini-2.5-flash', max_length=100, verbose_name='Modelo Gemini')),
                ('system_prompt', models.TextField(default='Você é o assistente virtual da marca Fersie. Responda a dúvidas de estoque, vendas e relatórios financeiros com dados precisos.', verbose_name='Instrução do Sistema (System Prompt)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Ativo')),
                ('temperature', models.FloatField(default=0.7, verbose_name='Temperatura')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Configuração do Assistente de IA',
                'verbose_name_plural': 'Configurações do Assistente de IA',
            },
        ),
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('user', 'Usuário'), ('assistant', 'Assistente')], default='user', max_length=20)),
                ('content', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chat_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Mensagem do Chat',
                'verbose_name_plural': 'Mensagens do Chat',
                'ordering': ['timestamp'],
            },
        ),
    ]
