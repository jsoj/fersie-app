from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('new/', views.new_conversation, name='new_conversation'),
    path('delete/<int:conversation_id>/', views.delete_conversation, name='delete_conversation'),
    path('stream/', views.chat_stream, name='chat_stream'),
    path('message/', views.chat_message_htmx, name='chat_message_htmx'),
    path('query/', views.query_ai, name='query'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
]

