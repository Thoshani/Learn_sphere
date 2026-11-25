from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create demo accounts (demo_student / demo123, demo_admin / admin123)."

    def handle(self, *args, **opts):
        User = get_user_model()
        for username, pw, role, first in [("demo_student", "demo123", "user", "Alex"),
                                          ("demo_admin", "admin123", "admin", "Admin")]:
            u, created = User.objects.get_or_create(
                username=username, defaults={"first_name": first, "email": f"{username}@demo.com", "role": role})
            u.role = role
            u.set_password(pw)
            u.save()
            self.stdout.write(f"{'Created' if created else 'Updated'} {username} / {pw}")
