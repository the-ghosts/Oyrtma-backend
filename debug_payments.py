#!/usr/bin/env python
"""Debug script to inspect payment and booking state."""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oyrtma_core.settings')
sys.path.insert(0, '/root/app' if os.path.exists('/root/app') else os.path.dirname(os.path.abspath(__file__)))
django.setup()

from api.models import Booking, Payment

print("=" * 80)
print("BOOKINGS (last 25)")
print("=" * 80)
bookings = Booking.objects.all().order_by('-id')[:25]
for b in bookings:
    print(f"{b.id:3} | Ref: {b.reference_id:12} | Status: {b.payment_status:7} | Amount: {b.amount_due:7} | Officer: {b.officer.username if b.officer else 'None':12}")

pending_count = Booking.objects.filter(payment_status='Pending').count()
paid_count = Booking.objects.filter(payment_status='Paid').count()
print(f"\nSummary: Total={Booking.objects.count()} | Pending={pending_count} | Paid={paid_count}")

print("\n" + "=" * 80)
print("PAYMENTS (last 20)")
print("=" * 80)
payments = Payment.objects.all().order_by('-id')[:20]
for p in payments:
    booking_ref = p.booking.reference_id if p.booking else 'DELETED'
    booking_status = p.booking.payment_status if p.booking else 'DELETED'
    print(f"{p.id:3} | Booking: {p.booking_id:3} (Ref: {booking_ref:12} Status: {booking_status:7}) | TransID: {p.transaction_id:30} | Amount: {p.amount}")

print(f"\nTotal Payments: {Payment.objects.count()}")
