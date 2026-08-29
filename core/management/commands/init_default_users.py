from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile

class Command(BaseCommand):
    help = 'Seeds default role accounts for Fersie App (Admin, Gerente, Caixa/Operador)'

    def handle(self, *args, **options):
        default_accounts = [
            {
                "username": "admin@fersie.com",
                "email": "admin@fersie.com",
                "password": "admin123",
                "first_name": "Admin",
                "last_name": "Fersie",
                "role": "ADMIN",
                "is_superuser": True,
                "is_staff": True,
            },
            {
                "username": "gerente@fersie.com",
                "email": "gerente@fersie.com",
                "password": "gerente123",
                "first_name": "Gerente",
                "last_name": "Fersie",
                "role": "MANAGER",
                "is_superuser": False,
                "is_staff": True,
            },
            {
                "username": "caixa@fersie.com",
                "email": "caixa@fersie.com",
                "password": "caixa123",
                "first_name": "Caixa",
                "last_name": "Fersie",
                "role": "STAFF",
                "is_superuser": False,
                "is_staff": True,
            },
            # Preseeded named role users matching test specifications
            {
                "username": "fernanda@fersie.com",
                "email": "fernanda@fersie.com",
                "password": "admin123",
                "first_name": "Fernanda",
                "last_name": "Fersie",
                "role": "ADMIN",
                "is_superuser": True,
                "is_staff": True,
            },
            {
                "username": "sibele@fersie.com",
                "email": "sibele@fersie.com",
                "password": "gerente123",
                "first_name": "Sibele",
                "last_name": "Fersie",
                "role": "MANAGER",
                "is_superuser": False,
                "is_staff": True,
            },
            {
                "username": "ieda@fersie.com",
                "email": "ieda@fersie.com",
                "password": "caixa123",
                "first_name": "Ieda",
                "last_name": "Fersie",
                "role": "STAFF",
                "is_superuser": False,
                "is_staff": True,
            },
        ]

        created_count = 0
        updated_count = 0

        for acc in default_accounts:
            user, created = User.objects.get_or_create(
                username=acc["username"],
                defaults={
                    "email": acc["email"],
                    "first_name": acc["first_name"],
                    "last_name": acc["last_name"],
                    "is_superuser": acc["is_superuser"],
                    "is_staff": acc["is_staff"],
                }
            )
            user.set_password(acc["password"])
            user.email = acc["email"]
            user.first_name = acc["first_name"]
            user.last_name = acc["last_name"]
            user.is_superuser = acc["is_superuser"]
            user.is_staff = acc["is_staff"]
            user.is_active = True
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = acc["role"]
            profile.save()

            if created:
                created_count += 1
            else:
                updated_count += 1

            self.stdout.write(
                self.style.SUCCESS(f"Seeded user '{acc['email']}' with role '{acc['role']}'.")
            )

        self.stdout.write(
            self.style.SUCCESS(f"Finished init_default_users. Created: {created_count}, Updated: {updated_count}")
        )
