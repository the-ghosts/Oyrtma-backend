"""
SMS message templates and constants for Termii integration
"""

# SMS Templates for different scenarios
SMS_TEMPLATES = {
    'fine_added': (
        "OYRTMA Alert: Traffic fine added to plate {plate_number}. "
        "Amount: ₦{amount}. "
        "Reference: {reference}. "
        "Pay online or visit the nearest office."
    ),
    'payment_reminder': (
        "OYRTMA Reminder: Outstanding fine on plate {plate_number}. "
        "Amount: ₦{amount}. "
        "Please pay to avoid penalties."
    ),
    'payment_confirmed': (
        "OYRTMA Receipt: Payment of ₦{amount} for plate {plate_number} confirmed. "
        "Reference: {reference}. Thank you!"
    ),
    'payment_failed': (
        "OYRTMA Alert: Payment verification failed for plate {plate_number}. "
        "Reference: {reference}. Please retry or contact support."
    ),
    'welcome': (
        "Welcome to OYRTMA Driver Portal! "
        "Use your driver's license to check traffic fines and pay online. "
        "Questions? Contact us for support."
    ),
}

# Termii Configuration
TERMII_MESSAGE_TYPE_SMS = 'text'
TERMII_MESSAGE_TYPE_WHATSAPP = 'whatsapp'
TERMII_CHANNEL_GENERIC = 'generic'
TERMII_CHANNEL_DND = 'dnd'  # Do Not Disturb - only for urgent messages

# SMS Retry Configuration
SMS_MAX_RETRIES = 3
SMS_RETRY_DELAY = 60  # seconds

# Phone number validation
PHONE_VALIDATION_PATTERNS = {
    'NG': r'^(\+234|0)[789]\d{9}$',  # Nigerian numbers
}

# Success response codes from Termii
TERMII_SUCCESS_CODES = ['success', '200', 'sent']

# Character limits
SMS_CHARACTER_LIMIT = 160
SMS_MULTIPART_CHARACTER_LIMIT = 153  # Reserve 7 chars for counter in multipart

