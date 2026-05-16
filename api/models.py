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


class Payment(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=255, null=True, blank=True)
    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} for {self.booking.reference_id} - {self.amount}"



# Create your models here.
