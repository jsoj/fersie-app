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
