"""
Celery tasks for SMS notification and other async operations
"""

import logging
from celery import shared_task
from django.utils import timezone
from api.models import Booking, SMSLog, DriverInformation
from api.services import get_sms_service, TermiiSMSException
from api.constants import SMS_TEMPLATES

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_sms_to_driver(self, booking_id: int, driver_id: int, template_key: str = 'fine_added') -> dict:
    """
    Async task to send SMS notification to driver about their fine
    
    Retries up to 3 times on failure with 60-second delay
    
    Args:
        self: Celery task instance (for retries)
        booking_id: ID of the Booking (fine) record
        driver_id: ID of the DriverInformation record
        template_key: SMS template key to use
        
    Returns:
        dict: Task result with status and details
    """
    try:
        # Fetch the booking and driver records
        booking = Booking.objects.select_related('officer').get(id=booking_id)
        driver = DriverInformation.objects.get(id=driver_id)
        
        logger.info(f"🚀 Starting SMS task for Booking {booking_id}, Driver {driver_id}")
        
        # Get SMS template
        template = SMS_TEMPLATES.get(template_key, SMS_TEMPLATES['fine_added'])
        
        # Format message with booking details
        message = template.format(
            plate_number=booking.plate_number,
            amount=int(booking.amount_due),
            reference=booking.reference_id,
        )
        
        logger.debug(f"📝 Message template: {message}")
        
        # Create SMS log entry (pending status)
        sms_log = SMSLog.objects.create(
            booking=booking,
            driver_info=driver,
            phone_number=driver.phone_number,
            message=message,
            status='pending'
        )
        logger.info(f"📋 Created SMSLog {sms_log.id} with status=pending")
        
        # Get SMS service
        sms_service = get_sms_service()
        
        # Send SMS
        logger.info(f"📤 Sending SMS to {driver.phone_number}...")
        response = sms_service.send_sms(driver.phone_number, message)
        
        # Update SMS log with response
        if response.get('status') == 'success':
            sms_log.status = 'sent'
            sms_log.termii_response = response.get('raw_response', {})
            sms_log.sent_at = timezone.now()
            sms_log.save()
            
            logger.info(f"✅ SMS sent successfully (SMSLog {sms_log.id})")
            logger.info(f"   Message ID: {response.get('message_id')}")
            
            return {
                'status': 'success',
                'sms_log_id': sms_log.id,
                'message_id': response.get('message_id'),
                'phone_number': driver.phone_number,
            }
        else:
            # SMS failed but log was created
            sms_log.status = 'failed'
            sms_log.error_message = response.get('error', 'Unknown error')
            sms_log.termii_response = response.get('raw_response', {})
            sms_log.save()
            
            logger.warning(f"⚠️ SMS send failed (SMSLog {sms_log.id})")
            logger.warning(f"   Error: {sms_log.error_message}")
            
            # Retry the task
            raise Exception(f"SMS send failed: {sms_log.error_message}")
    
    except DriverInformation.DoesNotExist:
        logger.error(f"❌ Driver {driver_id} not found")
        return {'status': 'error', 'reason': 'Driver not found'}
    
    except Booking.DoesNotExist:
        logger.error(f"❌ Booking {booking_id} not found")
        return {'status': 'error', 'reason': 'Booking not found'}
    
    except TermiiSMSException as e:
        logger.error(f"❌ Termii SMS Exception: {str(e)}")
        
        # Mark SMS log as failed if it exists
        try:
            sms_log = SMSLog.objects.filter(booking_id=booking_id).latest('created_at')
            sms_log.status = 'failed'
            sms_log.error_message = str(e)
            sms_log.save()
        except SMSLog.DoesNotExist:
            pass
        
        # Retry with exponential backoff
        retry_count = self.request.retries
        countdown = (2 ** retry_count) * 60  # 60s, 120s, 240s
        
        logger.info(f"🔄 Retrying SMS task (attempt {retry_count + 1}/3) in {countdown}s")
        raise self.retry(exc=e, countdown=countdown)
    
    except Exception as e:
        logger.error(f"❌ Unexpected error in SMS task: {str(e)}")
        
        # Mark SMS log as failed
        try:
            sms_log = SMSLog.objects.filter(booking_id=booking_id).latest('created_at')
            sms_log.status = 'failed'
            sms_log.error_message = f"Task error: {str(e)}"
            sms_log.save()
        except SMSLog.DoesNotExist:
            pass
        
        # Retry
        retry_count = self.request.retries
        countdown = (2 ** retry_count) * 60
        
        logger.info(f"🔄 Retrying SMS task (attempt {retry_count + 1}/3) in {countdown}s")
        raise self.retry(exc=e, countdown=countdown)


@shared_task
def retry_failed_sms(sms_log_id: int) -> dict:
    """
    Retry sending a previously failed SMS
    
    Args:
        sms_log_id: ID of the failed SMSLog record
        
    Returns:
        dict: Result of retry attempt
    """
    try:
        sms_log = SMSLog.objects.get(id=sms_log_id)
        
        logger.info(f"🔄 Retrying failed SMS {sms_log_id}")
        
        if not sms_log.booking or not sms_log.driver_info:
            logger.error(f"❌ SMS log missing booking or driver info")
            return {'status': 'error', 'reason': 'Missing booking or driver info'}
        
        # Resend the SMS
        sms_service = get_sms_service()
        response = sms_service.send_sms(sms_log.phone_number, sms_log.message)
        
        if response.get('status') == 'success':
            sms_log.status = 'sent'
            sms_log.termii_response = response.get('raw_response', {})
            sms_log.sent_at = timezone.now()
            sms_log.save()
            
            logger.info(f"✅ Failed SMS retried successfully (SMSLog {sms_log_id})")
            return {'status': 'success', 'sms_log_id': sms_log_id}
        else:
            sms_log.error_message = response.get('error', 'Unknown error')
            sms_log.save()
            
            logger.warning(f"⚠️ Retry still failed for SMS {sms_log_id}")
            return {'status': 'failed', 'error': sms_log.error_message}
    
    except SMSLog.DoesNotExist:
        logger.error(f"❌ SMSLog {sms_log_id} not found")
        return {'status': 'error', 'reason': 'SMSLog not found'}
    
    except Exception as e:
        logger.error(f"❌ Error retrying SMS {sms_log_id}: {str(e)}")
        return {'status': 'error', 'reason': str(e)}


@shared_task
def send_payment_confirmation_sms(booking_id: int) -> dict:
    """
    Send payment confirmation SMS to driver
    
    Args:
        booking_id: ID of the Booking (fine) record that was paid
        
    Returns:
        dict: Task result
    """
    try:
        booking = Booking.objects.get(id=booking_id, payment_status='Paid')
        
        # Look up driver by plate number
        driver = DriverInformation.objects.get(plate_number=booking.plate_number)
        
        logger.info(f"📨 Sending payment confirmation SMS for Booking {booking_id}")
        
        # Get payment confirmation template
        template = SMS_TEMPLATES.get('payment_confirmed')
        message = template.format(
            plate_number=booking.plate_number,
            amount=int(booking.amount_due),
            reference=booking.reference_id,
        )
        
        # Create SMS log
        sms_log = SMSLog.objects.create(
            booking=booking,
            driver_info=driver,
            phone_number=driver.phone_number,
            message=message,
            status='pending'
        )
        
        # Send SMS
        sms_service = get_sms_service()
        response = sms_service.send_sms(driver.phone_number, message)
        
        if response.get('status') == 'success':
            sms_log.status = 'sent'
            sms_log.termii_response = response.get('raw_response', {})
            sms_log.sent_at = timezone.now()
            sms_log.save()
            
            logger.info(f"✅ Payment confirmation SMS sent (SMSLog {sms_log.id})")
            return {'status': 'success', 'sms_log_id': sms_log.id}
        else:
            sms_log.status = 'failed'
            sms_log.error_message = response.get('error')
            sms_log.save()
            
            logger.warning(f"⚠️ Payment confirmation SMS failed for Booking {booking_id}")
            return {'status': 'failed', 'error': sms_log.error_message}
    
    except Booking.DoesNotExist:
        logger.error(f"❌ Paid Booking {booking_id} not found")
        return {'status': 'error', 'reason': 'Booking not found'}
    
    except DriverInformation.DoesNotExist:
        logger.error(f"❌ Driver not found for Booking {booking_id}")
        return {'status': 'error', 'reason': 'Driver not found'}
    
    except Exception as e:
        logger.error(f"❌ Error sending payment confirmation SMS: {str(e)}")
        return {'status': 'error', 'reason': str(e)}
