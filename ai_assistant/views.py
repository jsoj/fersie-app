from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from .models import AIAssistantConfig, ChatMessage
from .services import AIAssistantService

def chat_view(request):
    """
    Renders full-page AI Chat interface.
    """
    config = AIAssistantConfig.get_solo()
    messages_list = ChatMessage.objects.all().order_by('timestamp')
    
    context = {
        'config': config,
        'messages': messages_list,
    }
    return render(request, 'ai_assistant/chat.html', context)


@require_POST
def chat_message_htmx(request):
    """
    HTMX endpoint: receives user prompt via POST, stores user message,
    queries AIAssistantService, stores AI response, and returns HTML partial bubble.
    """
    prompt = request.POST.get('prompt', '').strip()
    if not prompt:
        return HttpResponse('')

    user = request.user if request.user.is_authenticated else None

    # Store user message
    user_msg = ChatMessage.objects.create(
        user=user,
        role='user',
        content=prompt
    )

    # Query AI Service
    ai_response_text = AIAssistantService.query_ai(prompt, user=user)

    # Store AI response message
    assistant_msg = ChatMessage.objects.create(
        user=user,
        role='assistant',
        content=ai_response_text
    )

    context = {
        'user_msg': user_msg,
        'assistant_msg': assistant_msg,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'ai_assistant/partials/chat_message.html', context)

    # Fallback non-HTMX response
    return chat_view(request)


def query_ai(request):
    """
    JSON API endpoint for backward compatibility / external queries.
    """
    if request.method == 'POST':
        prompt = request.POST.get('prompt', '').strip()
        if not prompt:
            return JsonResponse({'error': 'Prompt não pode ser vazio.'}, status=400)

        user = request.user if request.user.is_authenticated else None

        ChatMessage.objects.create(
            user=user,
            role='user',
            content=prompt
        )

        response_text = AIAssistantService.query_ai(prompt, user=user)

        assistant_msg = ChatMessage.objects.create(
            user=user,
            role='assistant',
            content=response_text
        )

        return JsonResponse({
            'response': response_text,
            'timestamp': assistant_msg.timestamp.isoformat()
        })

    return JsonResponse({'error': 'Somente POST é permitido.'}, status=400)


from django.views.decorators.csrf import csrf_exempt
import json
import requests

@csrf_exempt
def whatsapp_webhook(request):
    """
    Webhook endpoint para Evolution API (fersie_bot).
    Recebe mensagens do WhatsApp, consulta o AIAssistantService e responde via Evolution API.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Somente método POST é permitido.'}, status=405)

    config = AIAssistantConfig.get_solo()
    if not config.is_active or not getattr(config, 'whatsapp_integration_active', True):
        return JsonResponse({'status': 'disabled', 'message': 'Integração de IA / WhatsApp inativa.'})

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'JSON inválido.'}, status=400)

    event = payload.get('event')
    if event == 'messages.upsert':
        data = payload.get('data', {})
        key = data.get('key', {})
        from_me = key.get('fromMe', False)
        remote_jid = key.get('remoteJid', '')

        if not from_me and remote_jid:
            message_obj = data.get('message', {})
            text = (
                message_obj.get('conversation') or
                message_obj.get('extendedTextMessage', {}).get('text') or
                ''
            ).strip()

            if text:
                # Registra mensagem de entrada
                ChatMessage.objects.create(role='user', content=f"[WhatsApp {remote_jid}] {text}")

                # Consulta Inteligência Artificial com contexto RAG do banco
                ai_reply = AIAssistantService.query_ai(text)

                # Registra resposta da IA
                ChatMessage.objects.create(role='assistant', content=f"[WhatsApp {remote_jid}] {ai_reply}")

                # Envia resposta via Evolution API se a chave de API estiver configurada
                if config.evolution_api_key:
                    send_url = f"{config.evolution_api_url.rstrip('/')}/message/sendText/{config.evolution_instance_name}"
                    headers = {
                        'apikey': config.evolution_api_key,
                        'Content-Type': 'application/json'
                    }
                    data_send = {
                        'number': remote_jid.split('@')[0],
                        'options': {'delay': 1200, 'presence': 'composing'},
                        'textMessage': {'text': ai_reply}
                    }
                    try:
                        requests.post(send_url, json=data_send, headers=headers, timeout=10)
                    except Exception as e:
                        print(f"Erro ao enviar resposta via Evolution API: {e}")

                return JsonResponse({'status': 'processed', 'reply': ai_reply})

    return JsonResponse({'status': 'ignored'})

