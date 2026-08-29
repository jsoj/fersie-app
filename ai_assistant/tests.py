import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from inventory.models import Product, Supplier, Category
from financial.models import Sale, Expense, AccountsReceivable
from ai_assistant.models import AIAssistantConfig, ChatMessage
from ai_assistant.services import AIAssistantService

User = get_user_model()

class AIAssistantModelTests(TestCase):
    def test_ai_assistant_config_defaults(self):
        config = AIAssistantConfig.get_solo()
        self.assertEqual(config.model_name, 'gemini-2.5-flash')
        self.assertEqual(config.temperature, 0.7)
        self.assertTrue(config.is_active)
        self.assertEqual(config.get_api_key(), '')

    def test_get_api_key_fallback(self):
        config = AIAssistantConfig.get_solo()
        config.api_key = ''
        config.save()
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_env_key'}):
            self.assertEqual(config.get_api_key(), 'test_env_key')

    def test_chat_message_properties(self):
        user = User.objects.create_user(username='testuser', password='password123')
        user_msg = ChatMessage.objects.create(user=user, role='user', content='Hello AI')
        asst_msg = ChatMessage.objects.create(user=user, role='assistant', content='Hello User')

        self.assertEqual(user_msg.user_prompt, 'Hello AI')
        self.assertEqual(user_msg.ai_response, '')
        self.assertEqual(asst_msg.ai_response, 'Hello User')
        self.assertEqual(asst_msg.user_prompt, '')
        self.assertIn("[USER] testuser", str(user_msg))


class AIAssistantServiceTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Alfaiataria")
        supplier = Supplier.objects.create(name="Supplier 1")
        Product.objects.create(
            cod_unico="P001",
            descricao="Blazer Silk",
            preco_custo=Decimal("100.00"),
            preco_venda=Decimal("250.00"),
            quantidade=2,
            category_obj=category
        )
        Product.objects.create(
            cod_unico="P002",
            descricao="Calça Linho",
            preco_custo=Decimal("50.00"),
            preco_venda=Decimal("150.00"),
            quantidade=10,
            category_obj=category
        )

        Sale.objects.create(
            sale_code="VENDA-001",
            gross_amount=Decimal("500.00"),
            discount=Decimal("50.00"),
            net_amount=Decimal("450.00"),
            status="completed"
        )
        Expense.objects.create(
            description="Aluguel",
            category="aluguel",
            amount=Decimal("200.00"),
            due_date="2026-08-30",
            status="pago"
        )
        AccountsReceivable.objects.create(
            customer_name="Cliente 1",
            total_amount=Decimal("300.00"),
            status="pendente"
        )

    def test_extract_database_context(self):
        context = AIAssistantService.extract_database_context()

        self.assertEqual(context['total_products'], 2)
        self.assertEqual(context['low_stock_items'], 1)
        self.assertEqual(context['total_inventory_value'], 2000.00)
        self.assertEqual(context['total_sales_revenue'], 450.00)
        self.assertEqual(context['total_expenses'], 200.00)
        self.assertEqual(context['net_profit'], 250.00)
        self.assertEqual(context['pending_receivables'], 300.00)

    def test_build_system_prompt_with_context(self):
        config = AIAssistantConfig.get_solo()
        full_prompt = AIAssistantService.build_system_prompt_with_context(config)

        self.assertIn("--- DADOS EM TEMPO REAL DO SISTEMA FERSIE ---", full_prompt)
        self.assertIn("Total de Produtos Cadastrados: 2", full_prompt)
        self.assertIn("Itens em Estoque Baixo (<= 3 unidades): 1", full_prompt)
        self.assertIn("Receita Total de Vendas (Concluídas): R$ 450.00", full_prompt)

    def test_query_ai_unconfigured_missing_key(self):
        config = AIAssistantConfig.get_solo()
        config.api_key = ''
        config.save()

        with patch.dict('os.environ', {'GEMINI_API_KEY': ''}):
            response = AIAssistantService.query_ai("Qual meu faturamento?")
            self.assertIn("não está configurado", response)

    def test_query_ai_inactive_config(self):
        config = AIAssistantConfig.get_solo()
        config.is_active = False
        config.save()

        response = AIAssistantService.query_ai("Qual meu faturamento?")
        self.assertIn("desativado", response)

    @patch('urllib.request.urlopen')
    def test_query_ai_successful_gemini_api_call(self, mock_urlopen):
        config = AIAssistantConfig.get_solo()
        config.api_key = 'test_key'
        config.save()

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "O faturamento atual da Fersie é de R$ 450,00."}
                        ]
                    }
                }
            ]
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        response = AIAssistantService.query_ai("Qual é o faturamento da loja?")
        self.assertEqual(response, "O faturamento atual da Fersie é de R$ 450,00.")

    @patch('urllib.request.urlopen')
    def test_query_ai_network_error_handling(self, mock_urlopen):
        config = AIAssistantConfig.get_solo()
        config.api_key = 'test_key'
        config.save()

        mock_urlopen.side_effect = Exception("Connection timeout")

        response = AIAssistantService.query_ai("Qual é o faturamento?")
        self.assertIn("indisponível", response)


class AIAssistantViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='adminuser', password='password123')

    def test_chat_view_render(self):
        url = reverse('ai_assistant:chat')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ai_assistant/chat.html')

    @patch.object(AIAssistantService, 'query_ai')
    def test_chat_message_htmx_post(self, mock_query_ai):
        mock_query_ai.return_value = "Atualmente você possui 0 itens sem estoque."

        self.client.login(username='adminuser', password='password123')
        url = reverse('ai_assistant:chat_message_htmx')

        response = self.client.post(
            url,
            {'prompt': 'Quais produtos estão sem estoque?'},
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'ai_assistant/partials/chat_message.html')
        self.assertContains(response, 'Quais produtos estão sem estoque?')
        self.assertContains(response, 'Atualmente você possui 0 itens sem estoque.')

        user_msg = ChatMessage.objects.filter(role='user').first()
        asst_msg = ChatMessage.objects.filter(role='assistant').first()

        self.assertIsNotNone(user_msg)
        self.assertIsNotNone(asst_msg)
        self.assertEqual(user_msg.content, 'Quais produtos estão sem estoque?')
        self.assertEqual(asst_msg.content, 'Atualmente você possui 0 itens sem estoque.')

    @patch.object(AIAssistantService, 'query_ai')
    def test_query_ai_json_endpoint(self, mock_query_ai):
        mock_query_ai.return_value = "Resposta de teste JSON."
        url = reverse('ai_assistant:query')

        response = self.client.post(url, {'prompt': 'Teste JSON'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['response'], "Resposta de teste JSON.")
        self.assertIn('timestamp', data)
