from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import Booking

User = get_user_model()

class Command(BaseCommand):
    help = 'Backfill Bookings with NULL officer to a system user (system_generated)'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='system_generated', help='Username for the system user')
        parser.add_argument('--assign-to', type=str, help='If provided, use an existing username to assign instead of creating system_generated')

    def handle(self, *args, **options):
        username = options.get('username')
        assign_to = options.get('assign_to')

        if assign_to:
            try:
                user = User.objects.get(username=assign_to)
                self.stdout.write(self.style.SUCCESS(f'Using existing user `{assign_to}` for backfill.'))
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'User `{assign_to}` does not exist.'))
                return
        else:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'is_active': False,
                    'first_name': 'System',
                    'last_name': 'Generated'
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created system user `{username}`.'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Using existing system user `{username}`.'))

        null_count = Booking.objects.filter(officer__isnull=True).count()
        if null_count == 0:
            self.stdout.write(self.style.WARNING('No bookings found with NULL officer.'))
            return

        Booking.objects.filter(officer__isnull=True).update(officer=user)
        self.stdout.write(self.style.SUCCESS(f'Updated {null_count} bookings to have officer `{user.username}`.'))
