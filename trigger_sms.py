import os
import sys
import time

# Add django project root to python path
sys.path.insert(0, r"c:\Users\User\Documents\Django_Project\Oyrtma\Oyrtma-backend\oyrtma_core")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oyrtma_core.settings')
import django
django.setup()

from api.models import DriverInformation, Offender, Vehicle, Offence, Booking, User, SMSLog

def main():
    print("=== END-TO-END SMS NOTIFICATION TEST ===")
    
    # 1. Get or create Officer
    officer = User.objects.filter(is_officer=True).first()
    if not officer:
        # Fallback to any staff user or create a new one
        officer = User.objects.filter(is_staff=True).first()
        if not officer:
            officer = User.objects.create_user(
                username="test_officer_sms",
                password="password123",
                is_officer=True,
                is_staff=True
            )
            print(f"Created temporary officer: {officer.username}")
    print(f"Using Officer: {officer.username}")

    # 2. Get or create Offence
    offence = Offence.objects.filter(code="SPD-01").first()
    if not offence:
        offence = Offence.objects.create(
            name="Over Speeding",
            code="SPD-01",
            description="Exceeding the speed limit on a state road.",
            fine_amount=10000.00
        )
        print(f"Created temporary offence: {offence.name}")
    print(f"Using Offence: {offence.name}")

    # 3. Create a test Offender
    ref_num = int(time.time())
    offender = Offender.objects.create(
        driver_license_number=f"DL-{ref_num}",
        driver_name="Stella Test Offender",
        email=f"stella_{ref_num}@test.com",
        phone_number="+2349157405905"
    )
    print(f"Created test Offender: {offender.driver_name} (License: {offender.driver_license_number})")

    # 4. Create Vehicle with plate matching a DriverInformation record with +2349157405905
    test_plate = "AB-910-CQZ" # Stella Williams' plate in DriverInformation
    Vehicle.objects.filter(plate_number=test_plate).delete()
    vehicle = Vehicle.objects.create(
        owner=offender,
        plate_number=test_plate,
        vehicle_model="Toyota Corolla"
    )
    print(f"Created Vehicle for Offender: {vehicle.plate_number}")

    # Verify matching DriverInformation exists
    driver_info = DriverInformation.objects.filter(plate_number=test_plate, is_active=True).first()
    if driver_info:
        print(f"Verified matching DriverInformation record exists: Name: {driver_info.driver_name}, Phone: {driver_info.phone_number}")
    else:
        print("WARNING: No matching active DriverInformation record found for plate!")

    # 5. Create Booking (triggers signal)
    booking_ref = f"BK-TEST-{ref_num}"
    print(f"\nCreating Booking with ref: {booking_ref} ...")
    
    booking = Booking.objects.create(
        offence=offence,
        offender=offender,
        officer=officer,
        reference_id=booking_ref,
        amount_due=offence.fine_amount,
        location="Iwo Road, Ibadan"
    )
    print(f"Booking {booking.id} created successfully!")

    print("\nWaiting 6 seconds for Celery worker to pick up the task and query Termii API...")
    time.sleep(6)

    # 6. Retrieve SMS logs
    print("\n=== SMS LOGS FOR BOOKING ===")
    logs = SMSLog.objects.filter(booking=booking)
    if logs.exists():
        for log in logs:
            print(f"Log ID: {log.id}")
            print(f"Phone Number: {log.phone_number}")
            print(f"Message: {log.message}")
            print(f"Status: {log.status.upper()}")
            print(f"Error Message: {log.error_message}")
            print(f"Termii Response: {log.termii_response}")
            print("-" * 40)
    else:
        print("No SMS logs found! Check if Celery worker is running and configured correctly.")

if __name__ == "__main__":
    main()
