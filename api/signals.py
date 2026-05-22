"""
Django signals to automatically trigger SMS notifications on events
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from api.models import Booking, DriverInformation
from api.tasks import send_sms_to_driver, send_payment_confirmation_sms

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def send_fine_notification_sms(sender, instance, created, **kwargs):
    """
    Signal handler to send SMS notification when a new booking (fine) is created
    
    Workflow:
    1. Check if booking is newly created
    2. Look up plate number in DriverInformation database
    3. If found, queue async SMS task via Celery
    4. If not found, log warning but don't break fine creation
    
    Args:
        sender: Model that sent the signal (Booking)
        instance: Instance of the Booking being saved
        created: Boolean indicating if this is a new record
    """
    
    if not created:
        # Only process new bookings, not updates
        logger.debug(f"Booking {instance.id} updated (not new), skipping SMS")
        return
    
    if not instance.plate_number:
        logger.warning(f"Booking {instance.id} has no plate number, cannot send SMS")
        return
    
    try:
        # Look up driver by plate number
        driver = DriverInformation.objects.get(plate_number=instance.plate_number, is_active=True)
        
        logger.info(f"✅ Found driver for plate {instance.plate_number}")
        logger.info(f"   Queueing SMS task for Booking {instance.id} → {driver.phone_number}")
        
        # Queue async SMS task
        send_sms_to_driver.delay(
            booking_id=instance.id,
            driver_id=driver.id,
            template_key='fine_added'
        )
        
        logger.info(f"🚀 SMS task queued for Booking {instance.id}")
    
    except DriverInformation.DoesNotExist:
        logger.warning(
            f"⚠️ Driver not found for plate {instance.plate_number}. "
            f"Booking {instance.id} created but SMS not sent."
        )
        # Don't raise exception - let the booking be created even if driver not found
    
    except DriverInformation.MultipleObjectsReturned:
        logger.warning(
            f"⚠️ Multiple drivers found for plate {instance.plate_number}. "
            f"This shouldn't happen (plate should be unique). "
            f"Booking {instance.id} created but SMS not sent."
        )
    
    except Exception as e:
        logger.error(f"❌ Error in fine_notification signal: {str(e)}")
        # Don't raise exception - let the booking be created


@receiver(post_save, sender=Booking)
def send_payment_confirmation_sms_signal(sender, instance, created, update_fields, **kwargs):
    """
    Signal handler to send payment confirmation SMS when booking is marked as paid
    
    Triggers when:
    - Booking status changes from 'Pending' to 'Paid'
    - payment_status field is updated
    
    Args:
        sender: Model that sent the signal (Booking)
        instance: Instance of the Booking being saved
        created: Boolean indicating if this is a new record
        update_fields: Set of fields that were updated (only for post_save with update)
    """
    
    # Only process updates, not new bookings
    if created:
        return
    
    # Check if payment_status was updated
    if update_fields and 'payment_status' not in update_fields:
        logger.debug(f"Booking {instance.id} updated but payment_status not changed")
        return
    
    # Only send SMS if payment status is now 'Paid'
    if instance.payment_status != 'Paid':
        logger.debug(f"Booking {instance.id} payment_status is {instance.payment_status}, not 'Paid'")
        return
    
    logger.info(f"✅ Booking {instance.id} marked as Paid, queueing payment confirmation SMS")
    
    try:
        # Queue async payment confirmation SMS task
        send_payment_confirmation_sms.delay(booking_id=instance.id)
        logger.info(f"🚀 Payment confirmation SMS task queued for Booking {instance.id}")
    
    except Exception as e:
        logger.error(f"❌ Error queuing payment confirmation SMS: {str(e)}")
