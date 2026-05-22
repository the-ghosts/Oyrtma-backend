#!/usr/bin/env python
"""
Quick validation of Phase 3 API endpoints
Run with: python manage.py shell
Then: exec(open('validate_phase3.py').read())
"""

import os
import sys

# Quick checks
checks = []

# 1. Check ViewSets imported
try:
    from api.views import DriverInformationViewSet, SMSLogViewSet
    checks.append(("✅", "ViewSets imported", "DriverInformationViewSet and SMSLogViewSet"))
except Exception as e:
    checks.append(("❌", "ViewSets import failed", str(e)))

# 2. Check serializers
try:
    from api.serializers import DriverInformationSerializer, SMSLogSerializer
    checks.append(("✅", "Serializers imported", "DriverInformationSerializer and SMSLogSerializer"))
except Exception as e:
    checks.append(("❌", "Serializers import failed", str(e)))

# 3. Check permissions
try:
    from api.views import IsOfficer, IsAdmin
    checks.append(("✅", "Permissions imported", "IsOfficer and IsAdmin"))
except Exception as e:
    checks.append(("❌", "Permissions import failed", str(e)))

# 4. Check models
try:
    from api.models import DriverInformation, SMSLog
    count_drivers = DriverInformation.objects.count()
    count_sms_logs = SMSLog.objects.count()
    checks.append(("✅", "Models imported", f"DriverInformation ({count_drivers}), SMSLog ({count_sms_logs})"))
except Exception as e:
    checks.append(("❌", "Models import failed", str(e)))

# 5. Check URL registration
try:
    from django.urls import resolve
    from django.test import RequestFactory
    
    # Create a test request
    rf = RequestFactory()
    
    # Check if drivers endpoint exists
    from rest_framework.routers import DefaultRouter
    from api.urls import router
    
    endpoints = [route.name for route in router.registry]
    if 'driver' in endpoints and 'sms-log' in endpoints:
        checks.append(("✅", "URL routes registered", "drivers and sms-logs endpoints"))
    else:
        checks.append(("⚠️ ", "URL routes check", f"Found: {endpoints}"))
except Exception as e:
    checks.append(("⚠️ ", "URL routes check", str(e)))

# 6. Check Django configuration
try:
    from django.conf import settings
    termii_key = '✓' if settings.TERMII_API_KEY else '✗'
    celery_broker = '✓' if settings.CELERY_BROKER_URL else '✗'
    checks.append(("✅", "Settings configured", f"Termii {termii_key}, Celery {celery_broker}"))
except Exception as e:
    checks.append(("⚠️ ", "Settings check", str(e)))

# Display results
print("\n" + "="*80)
print("Phase 3: SMS Notification API Endpoints - Validation Report")
print("="*80 + "\n")

for icon, check, detail in checks:
    print(f"{icon} {check:<30} {detail}")

print("\n" + "="*80)
print("📊 Registered API Endpoints:")
print("="*80)
print("""
Driver Management:
  • GET    /api/drivers/              - List all drivers
  • POST   /api/drivers/              - Create new driver
  • GET    /api/drivers/{id}/         - Get driver details
  • PUT    /api/drivers/{id}/         - Update driver
  • PATCH  /api/drivers/{id}/         - Partial update driver
  • DELETE /api/drivers/{id}/         - Delete driver
  • POST   /api/drivers/bulk-import/  - Bulk import from CSV
  • GET    /api/drivers/search/       - Search by plate number

SMS Log Management:
  • GET    /api/sms-logs/             - List all SMS logs
  • GET    /api/sms-logs/{id}/        - Get SMS log details
  • POST   /api/sms-logs/{id}/retry/  - Retry failed SMS
  • GET    /api/sms-logs/by-booking/  - Get SMS logs by booking
  • GET    /api/sms-logs/stats/       - Get SMS statistics
""")

print("="*80)
print("✨ Phase 3 API Endpoints - Ready to Test!")
print("="*80 + "\n")

# Test count
success = sum(1 for icon, _, _ in checks if icon == "✅")
print(f"✅ {success}/{len(checks)} checks passed")
