from django.contrib import admin
from .models import AIAssistantConfig, ChatMessage

@admin.register(AIAssistantConfig)
class AIAssistantConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'model_name', 'temperature', 'is_active', 'updated_at')
    list_filter = ('is_active', 'model_name')
    readonly_fields = ('updated_at', 'created_at')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'role', 'short_content', 'timestamp')
    list_filter = ('role', 'timestamp', 'user')
    readonly_fields = ('timestamp',)

    def short_content(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    short_content.short_description = "Conteúdo"
