#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oyrtma_core.settings')
django.setup()

from api.models import DriverInformation
from django.db.models import Count

print('=== PHONE NUMBER DISTRIBUTION ===')
stats = DriverInformation.objects.values('phone_number').annotate(count=Count('id')).order_by('-count')
for s in stats:
    print(f"{s['phone_number']}: {s['count']} drivers")

print(f"\n✅ Total drivers: {DriverInformation.objects.count()}")
print(f"✅ Unique phone numbers: {stats.count()}")
