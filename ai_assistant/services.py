import json
import logging
from decimal import Decimal
import urllib.request
import urllib.error
from django.db.models import Sum
from inventory.models import Product
from financial.models import Sale, Expense, AccountsReceivable
from .models import AIAssistantConfig, ChatMessage

logger = logging.getLogger(__name__)

class AIAssistantService:
    @staticmethod
    def extract_database_context():
        """
        Extract real-time database statistics from inventory and financial apps.
        """
        # Inventory Context
        total_products = Product.objects.count()
        low_stock_items = Product.objects.filter(quantidade__lte=3).count()
        total_inventory_value = sum(
            (p.preco_venda or Decimal('0.00')) * (p.quantidade or 0)
            for p in Product.objects.all()
        )

        # Financial Context
        completed_sales = Sale.objects.filter(status='completed')
        total_sales_revenue = completed_sales.aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')

        total_expenses = Expense.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        net_profit = total_sales_revenue - total_expenses

        pending_receivables = AccountsReceivable.objects.filter(status='pendente').aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

        return {
            'total_products': total_products,
            'low_stock_items': low_stock_items,
            'total_inventory_value': float(total_inventory_value),
            'total_sales_revenue': float(total_sales_revenue),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit),
            'pending_receivables': float(pending_receivables),
        }

    @classmethod
    def build_system_prompt_with_context(cls, config):
        """
        Builds the system instruction string injecting real-time database RAG context.
        """
        base_prompt = config.system_prompt if config and config.system_prompt else (
            "Você é o assistente virtual da marca Fersie. "
            "Responda a dúvidas de estoque, vendas e relatórios financeiros com dados precisos."
        )

        context = cls.extract_database_context()

        rag_context = (
            f"\n\n--- DADOS EM TEMPO REAL DO SISTEMA FERSIE ---\n"
            f"Estoque:\n"
            f"- Total de Produtos Cadastrados: {context['total_products']}\n"
            f"- Itens em Estoque Baixo (<= 3 unidades): {context['low_stock_items']}\n"
            f"- Valor Total do Estoque (Preço de Venda): R$ {context['total_inventory_value']:.2f}\n\n"
            f"Financeiro:\n"
            f"- Receita Total de Vendas (Concluídas): R$ {context['total_sales_revenue']:.2f}\n"
            f"- Total de Despesas Registradas: R$ {context['total_expenses']:.2f}\n"
            f"- Lucro Líquido: R$ {context['net_profit']:.2f}\n"
            f"- Contas a Receber Pendentes: R$ {context['pending_receivables']:.2f}\n"
            f"--------------------------------------------------\n"
            f"Use estes dados reais para responder ao usuário sempre que ele perguntar sobre "
            f"estoque, vendas, despesas, faturamento ou finanças."
        )

        return base_prompt + rag_context

    @classmethod
    def query_ai(cls, user_prompt, user=None):
        """
        Queries Google Gemini API with system prompt + RAG context injection.
        Returns authentic AI text response or polite fallback message if unconfigured/offline.
        """
        config = AIAssistantConfig.get_solo()

        if not config or not config.is_active:
            return "O assistente de IA está temporariamente desativado nas configurações do sistema."

        api_key = config.get_api_key()
        if not api_key:
            return "O assistente de IA não está configurado. Por favor, cadastre a chave API do Gemini nas configurações."

        model_name = config.model_name or 'gemini-2.5-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        system_instruction_text = cls.build_system_prompt_with_context(config)

        payload = {
            "system_instruction": {
                "parts": [
                    {"text": system_instruction_text}
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": user_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": config.temperature if config.temperature is not None else 0.7
            }
        }

        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_bytes = resp.read()
                res_data = json.loads(resp_bytes.decode('utf-8'))

                candidates = res_data.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts:
                        return parts[0].get('text', '').strip()

                return "O assistente de IA respondeu sem conteúdo de texto legível."

        except urllib.error.HTTPError as err:
            logger.error(f"Gemini API HTTP Error {err.code}: {err.reason}")
            # Try fallback payload without system_instruction if 400
            if err.code == 400:
                try:
                    fallback_prompt = f"{system_instruction_text}\n\nPergunta do Usuário: {user_prompt}"
                    fallback_payload = {
                        "contents": [{"role": "user", "parts": [{"text": fallback_prompt}]}],
                        "generationConfig": {"temperature": config.temperature or 0.7}
                    }
                    req_fb = urllib.request.Request(
                        url,
                        data=json.dumps(fallback_payload).encode('utf-8'),
                        headers={'Content-Type': 'application/json'},
                        method='POST'
                    )
                    with urllib.request.urlopen(req_fb, timeout=15) as resp_fb:
                        res_fb = json.loads(resp_fb.read().decode('utf-8'))
                        cand_fb = res_fb.get('candidates', [])
                        if cand_fb:
                            parts_fb = cand_fb[0].get('content', {}).get('parts', [])
                            if parts_fb:
                                return parts_fb[0].get('text', '').strip()
                except Exception as fb_err:
                    logger.error(f"Fallback Gemini call failed: {fb_err}")

            return "Desculpe, ocorreu uma falha na requisição para o serviço de IA. Verifique a chave de API ou as configurações."

        except Exception as e:
            logger.error(f"Gemini API Exception: {e}")
            return "Desculpe, o serviço de IA está indisponível no momento. Por favor, tente novamente mais tarde."

    @classmethod
    def stream_ai(cls, conversation, user_prompt, user=None):
        """
        Streaming generator that queries Google Gemini API with streamGenerateContent (alt=sse),
        yielding Server-Sent Event (SSE) chunks in real-time.
        Saves the complete response and updates conversation title on finish.
        """
        config = AIAssistantConfig.get_solo()

        if not config or not config.is_active:
            err = "O assistente de IA está temporariamente desativado nas configurações do sistema."
            yield f"data: {json.dumps({'chunk': err})}\n\n"
            yield f"data: {json.dumps({'done': True, 'error': True})}\n\n"
            return

        api_key = config.get_api_key()
        if not api_key:
            err = "O assistente de IA não está configurado. Por favor, cadastre a chave API do Gemini nas configurações."
            yield f"data: {json.dumps({'chunk': err})}\n\n"
            yield f"data: {json.dumps({'done': True, 'error': True})}\n\n"
            return

        model_name = config.model_name or 'gemini-2.5-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={api_key}"

        system_instruction_text = cls.build_system_prompt_with_context(config)

        # Build contents with conversation history (last 10 messages for rich conversational context)
        contents = []
        if conversation:
            past_messages = conversation.messages.order_by('timestamp')
            for m in past_messages:
                if not m.content:
                    continue
                role = "user" if m.role == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": m.content}]
                })

        # Append current user prompt
        contents.append({
            "role": "user",
            "parts": [{"text": user_prompt}]
        })

        payload = {
            "system_instruction": {
                "parts": [
                    {"text": system_instruction_text}
                ]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": config.temperature if config.temperature is not None else 0.7
            }
        }

        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        full_response_parts = []

        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                for raw_line in resp:
                    line = raw_line.decode('utf-8', errors='replace').strip()
                    if not line:
                        continue
                    if line.startswith('data: '):
                        data_str = line[6:].strip()
                        if not data_str:
                            continue
                        try:
                            chunk_json = json.loads(data_str)
                            candidates = chunk_json.get('candidates', [])
                            if candidates:
                                parts = candidates[0].get('content', {}).get('parts', [])
                                if parts:
                                    text_piece = parts[0].get('text', '')
                                    if text_piece:
                                        full_response_parts.append(text_piece)
                                        yield f"data: {json.dumps({'chunk': text_piece})}\n\n"
                        except json.JSONDecodeError:
                            continue

        except urllib.error.HTTPError as err:
            logger.error(f"Gemini API HTTP Error {err.code}: {err.reason}")
            err_msg = f"Ocorreu um erro na requisição do serviço de IA ({err.code})."
            yield f"data: {json.dumps({'chunk': err_msg})}\n\n"
            full_response_parts.append(err_msg)
        except Exception as e:
            logger.error(f"Gemini API Streaming Exception: {e}")
            err_msg = "Desculpe, ocorreu uma instabilidade na conexão com o modelo de IA."
            yield f"data: {json.dumps({'chunk': err_msg})}\n\n"
            full_response_parts.append(err_msg)

        full_response_text = "".join(full_response_parts).strip()
        if not full_response_text:
            full_response_text = "O assistente de IA respondeu sem conteúdo legível."
            yield f"data: {json.dumps({'chunk': full_response_text})}\n\n"

        # Save assistant message to DB
        ChatMessage.objects.create(
            conversation=conversation,
            user=user,
            role='assistant',
            content=full_response_text
        )

        # Update conversation title if default or first message
        if conversation:
            if conversation.title in ("Nova Conversa", "", "Sem título"):
                cleaned_title = user_prompt.strip().replace('\n', ' ')
                if len(cleaned_title) > 35:
                    cleaned_title = cleaned_title[:35].rstrip() + "..."
                conversation.title = cleaned_title
            conversation.save()

        # Send final completion event
        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id if conversation else None, 'title': conversation.title if conversation else 'Conversa'})}\n\n"

