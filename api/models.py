from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

   
PAYMENT_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Cancelled', 'Cancelled'),
    ]

class User(AbstractUser):
    # Django handles username, password, email, first_name, last_name automatically.
    # We just add our custom OYRTMA roles:
    is_officer = models.BooleanField(default=False)
    is_citizen = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    badge_number = models.CharField(max_length=20, unique=True, null=True, blank=True) 

    def __str__(self):
        return f"{self.username} ({'Officer' if self.is_officer else 'Citizen'})"

class Offence (models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=15, unique=True)
    description = models.TextField()
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Offender (models.Model):
    
    driver_license_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    driver_name = models.CharField(max_length=255, null=True, blank=True)
    
    email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"{self.driver_name} - {self.driver_license_number}"

class Vehicle(models.Model):
    
    owner = models.ForeignKey(Offender, on_delete=models.CASCADE, related_name='vehicles') 
    plate_number = models.CharField(max_length=20, unique=True)
    vehicle_model = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.plate_number} (Owned by: {self.owner.driver_name})"

class Booking(models.Model):


    # Foreign Keys (Relationships)
    offence = models.ForeignKey(Offence, on_delete=models.PROTECT) # Changed to PROTECT so we can't accidentally delete an Offence if tickets exist for it
    offender = models.ForeignKey(Offender, on_delete=models.CASCADE)
    # Require an officer on every booking to ensure accountability. Use PROTECT to prevent
    # deleting a user who has issued tickets.
    officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    # Core Ticket Data
    reference_id = models.CharField(max_length=50, unique=True)
    amount_due = models.DecimalField(max_digits=10, decimal_places=2) # The frozen snapshot of the fine
    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='Pending')
    
    # Context & Evidence
    location = models.CharField(max_length=255)
    date_time = models.DateTimeField(auto_now_add=True)
    evidence_image = models.ImageField(upload_to='evidence/images/', null=True, blank=True)
    evidence_video = models.FileField(upload_to='evidence/videos/', null=True, blank=True)

    def __str__(self):
        return f"{self.reference_id} - {self.offender.driver_name} ({self.payment_status})"

    @property
    def plate_number(self):
        """
        Dynamically resolve the plate number from the offender's vehicles.
        Avoids database migrations while supporting SMS notification tasks.
        """
        first_vehicle = self.offender.vehicles.first()
        return first_vehicle.plate_number if first_vehicle else None


class Payment(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=255, null=True, blank=True)
    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} for {self.booking.reference_id} - {self.amount}"


class DriverInformation(models.Model):
    """
    Store driver information linked to plate numbers.
    Used for SMS notification lookup.
    A driver can have multiple vehicles (plate numbers).
    """
    plate_number = models.CharField(max_length=20, unique=True, db_index=True)
    phone_number = models.CharField(max_length=20, db_index=True)
    driver_name = models.CharField(max_length=100)
    state = models.CharField(max_length=50)  # e.g., "Lagos", "Abuja", "Oyo"
    license_number = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    vehicle_type = models.CharField(max_length=100, blank=True, null=True)  # e.g., "Toyota Camry", "Honda Civic"
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'driver_information'
        verbose_name = 'Driver Information'
        verbose_name_plural = 'Driver Information'
        indexes = [
            models.Index(fields=['plate_number']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['state']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.plate_number} - {self.driver_name}"


class SMSLog(models.Model):
    """
    Log all SMS notifications sent for audit and debugging.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='sms_logs', null=True, blank=True)
    driver_info = models.ForeignKey(DriverInformation, on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_logs')
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    termii_response = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sms_log'
        verbose_name = 'SMS Log'
        verbose_name_plural = 'SMS Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"SMS to {self.phone_number} - {self.status}"


# Create your models here.
