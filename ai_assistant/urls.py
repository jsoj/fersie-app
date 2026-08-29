from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('message/', views.chat_message_htmx, name='chat_message_htmx'),
    path('query/', views.query_ai, name='query'),
    path('whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
]

