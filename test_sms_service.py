#!/usr/bin/env python
"""
Test script for SMS service
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oyrtma_core.settings')
django.setup()

from api.services import get_sms_service, TermiiSMSException

print("=" * 60)
print("Testing Termii SMS Service")
print("=" * 60)

try:
    # Get SMS service
    sms_service = get_sms_service()
    print("\n✅ SMS Service initialized successfully")
    
    # Test phone number validation
    test_numbers = [
        '09157405905',
        '+2349157405905',
        '2349157405905',
    ]
    
    print("\n📱 Testing phone number validation:")
    for number in test_numbers:
        try:
            formatted = sms_service.validate_and_format_phone_number(number)
            print(f"  {number:20} → {formatted} ✅")
        except TermiiSMSException as e:
            print(f"  {number:20} → ERROR: {e} ❌")
    
    # Test message length
    print("\n📝 Testing message length info:")
    messages = [
        "Short message",
        "A" * 160,  # Exactly 160
        "B" * 200,  # Over 160
    ]
    
    for msg in messages:
        info = sms_service.get_message_length_info(msg)
        print(f"  Length: {info['length']:3d} → {info['parts']} part(s) {'(multipart)' if info['is_multipart'] else ''}")
    
    # Test SMS balance (if API is working)
    print("\n💰 Checking SMS balance:")
    balance = sms_service.check_sms_balance()
    if balance is not None:
        print(f"  Current balance: {balance} ✅")
    else:
        print(f"  Could not retrieve balance (Termii API may not be accessible) ⚠️")
    
    print("\n" + "=" * 60)
    print("✅ SMS Service tests completed successfully!")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ Error testing SMS service: {str(e)}")
    import traceback
    traceback.print_exc()
