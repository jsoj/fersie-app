from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from .models import AIAssistantConfig, ChatMessage, ChatConversation
from .services import AIAssistantService

def chat_view(request):
    """
    Renders full-page AI Chat interface with conversation sidebar, history, and streaming.
    """
    user = request.user if request.user.is_authenticated else None
    config = AIAssistantConfig.get_solo()

    conversations = ChatConversation.objects.all().order_by('-updated_at')
    if user:
        conversations = conversations.filter(user=user)

    conv_id = request.GET.get('c')
    current_conversation = None

    if conv_id:
        current_conversation = conversations.filter(id=conv_id).first()

    # If no conversation chosen, pick the most recent one or create one
    if not current_conversation:
        current_conversation = conversations.first()
        if not current_conversation:
            current_conversation = ChatConversation.objects.create(
                user=user,
                title='Nova Conversa'
            )
            conversations = ChatConversation.objects.filter(id=current_conversation.id)

    messages_list = current_conversation.messages.order_by('timestamp')

    context = {
        'config': config,
        'conversations': conversations,
        'current_conversation': current_conversation,
        'messages': messages_list,
    }
    return render(request, 'ai_assistant/chat.html', context)


def new_conversation(request):
    """
    Creates a new conversation and redirects to it.
    """
    user = request.user if request.user.is_authenticated else None
    conv = ChatConversation.objects.create(user=user, title='Nova Conversa')
    return redirect(f"/ai-assistant/?c={conv.id}")


@require_POST
def delete_conversation(request, conversation_id):
    """
    Deletes a conversation and all its messages.
    """
    user = request.user if request.user.is_authenticated else None
    qs = ChatConversation.objects.filter(id=conversation_id)
    if user and not user.is_superuser:
        qs = qs.filter(user=user)
    qs.delete()
    return redirect('ai_assistant:chat')


@require_POST
def chat_stream(request):
    """
    Streaming SSE endpoint: receives prompt and conversation_id via POST.
    Stores user message, streams AI chunks in real time, and persists assistant message.
    """
    prompt = request.POST.get('prompt', '').strip()
    conversation_id = request.POST.get('conversation_id')
    user = request.user if request.user.is_authenticated else None

    if not prompt:
        return JsonResponse({'error': 'Prompt vazio'}, status=400)

    # Find or create conversation
    conversation = None
    if conversation_id:
        conversation = ChatConversation.objects.filter(id=conversation_id).first()

    if not conversation:
        conversation = ChatConversation.objects.create(
            user=user,
            title='Nova Conversa'
        )

    # Save user message
    ChatMessage.objects.create(
        conversation=conversation,
        user=user,
        role='user',
        content=prompt
    )

    response = StreamingHttpResponse(
        AIAssistantService.stream_ai(conversation, prompt, user=user),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@require_POST
def chat_message_htmx(request):
    """
    HTMX fallback endpoint: receives user prompt via POST, stores user message,
    queries AIAssistantService, stores AI response, and returns HTML partial bubble.
    """
    prompt = request.POST.get('prompt', '').strip()
    conversation_id = request.POST.get('conversation_id')
    if not prompt:
        return HttpResponse('')

    user = request.user if request.user.is_authenticated else None

    conversation = None
    if conversation_id:
        conversation = ChatConversation.objects.filter(id=conversation_id).first()
    if not conversation:
        conversation = ChatConversation.objects.create(user=user, title='Nova Conversa')

    # Store user message
    user_msg = ChatMessage.objects.create(
        conversation=conversation,
        user=user,
        role='user',
        content=prompt
    )

    # Query AI Service
    ai_response_text = AIAssistantService.query_ai(prompt, user=user)

    # Store AI response message
    assistant_msg = ChatMessage.objects.create(
        conversation=conversation,
        user=user,
        role='assistant',
        content=ai_response_text
    )

    if conversation.title in ('Nova Conversa', '', 'Sem título'):
        cleaned = prompt.strip().replace('\n', ' ')
        conversation.title = cleaned[:35] + ('...' if len(cleaned) > 35 else '')
        conversation.save()

    context = {
        'user_msg': user_msg,
        'assistant_msg': assistant_msg,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'ai_assistant/partials/chat_message.html', context)

    return redirect(f"/ai-assistant/?c={conversation.id}")


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

