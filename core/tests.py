from django.test import TestCase
from django.contrib.auth.models import User
from django.core.management import call_command
from core.models import UserProfile

class DefaultUsersCommandTest(TestCase):
    def test_init_default_users_command(self):
        """Test init_default_users management command seeds required role accounts."""
        call_command('init_default_users')

        # Verify Admin role accounts
        admin_user = User.objects.get(username='admin@fersie.com')
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.check_password('admin123'))
        self.assertEqual(admin_user.profile.role, 'ADMIN')

        # Verify Gerente role accounts
        gerente_user = User.objects.get(username='gerente@fersie.com')
        self.assertTrue(gerente_user.is_staff)
        self.assertTrue(gerente_user.check_password('gerente123'))
        self.assertEqual(gerente_user.profile.role, 'MANAGER')

        # Verify Caixa/Operador role accounts
        caixa_user = User.objects.get(username='caixa@fersie.com')
        self.assertTrue(caixa_user.is_staff)
        self.assertTrue(caixa_user.check_password('caixa123'))
        self.assertEqual(caixa_user.profile.role, 'STAFF')

        # Verify Named preseeded users
        fernanda = User.objects.get(username='fernanda@fersie.com')
        self.assertEqual(fernanda.profile.role, 'ADMIN')
        
        sibele = User.objects.get(username='sibele@fersie.com')
        self.assertEqual(sibele.profile.role, 'MANAGER')

        ieda = User.objects.get(username='ieda@fersie.com')
        self.assertEqual(ieda.profile.role, 'STAFF')

    def test_init_default_users_idempotent(self):
        """Test init_default_users can be executed multiple times without duplicates or errors."""
        call_command('init_default_users')
        count_first = User.objects.count()
        call_command('init_default_users')
        count_second = User.objects.count()
        self.assertEqual(count_first, count_second)
