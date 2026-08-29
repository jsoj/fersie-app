import os
from django.db import models
from django.conf import settings

class AIAssistantConfig(models.Model):
    api_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Chave API (Gemini)",
        help_text="Opcional. Se em branco, utiliza a variável de ambiente GEMINI_API_KEY"
    )
    model_name = models.CharField(
        max_length=100,
        default='gemini-2.5-flash',
        verbose_name="Modelo Gemini"
    )
    system_prompt = models.TextField(
        default="Você é o assistente virtual da marca Fersie. Responda a dúvidas de estoque, vendas e relatórios financeiros com dados precisos.",
        verbose_name="Instrução do Sistema (System Prompt)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )
    temperature = models.FloatField(
        default=0.7,
        verbose_name="Temperatura"
    )
    evolution_api_url = models.CharField(
        max_length=255,
        default='https://evolution.projetobrasil2050.site',
        verbose_name="URL da Evolution API"
    )
    evolution_api_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Chave API (Evolution API)",
        help_text="Chave de autenticação apikey da Evolution API"
    )
    evolution_instance_name = models.CharField(
        max_length=100,
        default='fersie_bot',
        verbose_name="Nome da Instância WhatsApp"
    )
    whatsapp_integration_active = models.BooleanField(
        default=True,
        verbose_name="Integração WhatsApp Ativa"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do Assistente de IA"
        verbose_name_plural = "Configurações do Assistente de IA"

    def __str__(self):
        return f"AI Config ({self.model_name}) - {'Ativo' if self.is_active else 'Inativo'}"

    def get_api_key(self):
        if self.api_key and self.api_key.strip():
            return self.api_key.strip()
        return os.environ.get('GEMINI_API_KEY', '').strip()

    @classmethod
    def get_solo(cls):
        config = cls.objects.first()
        if not config:
            config = cls.objects.create(
                model_name='gemini-2.5-flash',
                system_prompt="Você é o assistente virtual da marca Fersie. Responda a dúvidas de estoque, vendas e relatórios financeiros com dados precisos.",
                is_active=True,
                temperature=0.7
            )
        return config


# Backward compatibility alias
AIConfiguration = AIAssistantConfig


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'Usuário'),
        ('assistant', 'Assistente'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        null=True,
        blank=True
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user'
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensagem do Chat"
        verbose_name_plural = "Mensagens do Chat"
        ordering = ['timestamp']

    def __str__(self):
        user_str = self.user.username if self.user else "Anônimo"
        return f"[{self.role.upper()}] {user_str} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    # Backward compatibility properties
    @property
    def user_prompt(self):
        return self.content if self.role == 'user' else ''

    @property
    def ai_response(self):
        return self.content if self.role == 'assistant' else ''
