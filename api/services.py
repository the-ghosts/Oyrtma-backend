"""
SMS notification service using Termii API
Handles sending SMS messages to drivers
"""

import logging
import requests
import re
from typing import Dict, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from .constants import (
    TERMII_MESSAGE_TYPE_SMS,
    TERMII_CHANNEL_GENERIC,
    SMS_CHARACTER_LIMIT,
    PHONE_VALIDATION_PATTERNS,
)

logger = logging.getLogger(__name__)


class TermiiSMSException(Exception):
    """Custom exception for Termii SMS errors"""
    pass


class TermiiSMSService:
    """
    Handle all SMS operations via Termii API
    
    Supports:
    - Sending single SMS
    - Phone number validation and formatting
    - Message length checking
    - Error handling and logging
    """

    def __init__(self):
        """Initialize Termii SMS service with API credentials"""
        self.api_key = settings.TERMII_API_KEY
        self.sender_id = settings.TERMII_SENDER_ID
        self.channel = settings.TERMII_CHANNEL
        self.base_url = "https://api.termii.com/api"
        self.timeout = getattr(settings, 'TERMII_TIMEOUT', 10)
        
        if not self.api_key:
            logger.error("❌ TERMII_API_KEY not configured in settings")
            raise TermiiSMSException("Termii API key not configured")
        
        logger.info("✅ Termii SMS Service initialized")

    def send_sms(self, phone_number: str, message: str, message_type: str = TERMII_MESSAGE_TYPE_SMS) -> Dict:
        """
        Send SMS via Termii API
        
        Args:
            phone_number: Recipient phone number (format: +234XXXXXXXXXX or 0XXXXXXXXXX)
            message: SMS message content
            message_type: Type of message ('text', 'whatsapp', etc.)
            
        Returns:
            dict: Response from Termii API with status and transaction ID
            
        Raises:
            TermiiSMSException: If API call fails or parameters are invalid
        """
        try:
            # Validate and format phone number
            formatted_phone = self.validate_and_format_phone_number(phone_number)
            
            # Check message length
            if len(message) > SMS_CHARACTER_LIMIT:
                logger.warning(f"⚠️ Message exceeds {SMS_CHARACTER_LIMIT} characters, will be split")
            
            # Prepare API request
            endpoint = f"{self.base_url}/sms/send"
            headers = {
                "Content-Type": "application/json",
            }
            
            payload = {
                "to": formatted_phone,
                "from": self.sender_id,
                "sms": message,
                "type": message_type,
                "channel": self.channel,
                "api_key": self.api_key,
            }
            
            logger.debug(f"📤 Sending SMS to {formatted_phone} via Termii...")
            
            # Make API request
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            
            try:
                response_data = response.json()
            except ValueError:
                response_data = {}
            
            # Check for success
            if response.status_code == 200:
                code = response_data.get('code')
                if code in ['ok', 'success', '200'] or 'message_id' in response_data:
                    logger.info(f"✅ SMS sent successfully to {formatted_phone}")
                    logger.debug(f"   Response: {response_data}")
                    return {
                        'status': 'success',
                        'message_id': response_data.get('message_id'),
                        'phone_number': formatted_phone,
                        'timestamp': timezone.now(),
                        'raw_response': response_data,
                    }
            
            # Extract detailed error message if available
            error_detail = response_data.get('message') or response_data.get('error')
            if not error_detail and response.status_code != 200:
                error_detail = f"HTTP {response.status_code} Error"
            elif not error_detail:
                error_detail = "Unknown error response from Termii"
                
            logger.warning(f"⚠️ Termii API returned failure: {error_detail}")
            logger.debug(f"   Response: {response_data}")
            return {
                'status': 'failed',
                'error': error_detail,
                'phone_number': formatted_phone,
                'timestamp': timezone.now(),
                'raw_response': response_data,
            }
        
        except requests.exceptions.Timeout:
            error_msg = "Termii API request timed out"
            logger.error(f"❌ {error_msg}")
            raise TermiiSMSException(error_msg)
        
        except requests.exceptions.RequestException as e:
            # Check if there is a response body to extract error from
            if hasattr(e, 'response') and e.response is not None:
                try:
                    resp_json = e.response.json()
                    err = resp_json.get('message') or resp_json.get('error')
                    if err:
                        logger.error(f"❌ Termii API error: {err}")
                        raise TermiiSMSException(err)
                except Exception:
                    pass
            error_msg = f"Failed to connect to Termii API: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise TermiiSMSException(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error sending SMS: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise TermiiSMSException(error_msg)

    def validate_and_format_phone_number(self, phone_number: str) -> str:
        """
        Validate and format phone number for Nigerian numbers
        
        Accepts formats:
        - +2349157405905
        - 09157405905
        - 2349157405905
        
        Returns:
        - +2349157405905 (standardized format)
        
        Args:
            phone_number: Phone number in various formats
            
        Returns:
            str: Formatted phone number in +234XXXXXXXXXX format
            
        Raises:
            TermiiSMSException: If phone number is invalid
        """
        if not phone_number or not isinstance(phone_number, str):
            raise TermiiSMSException("Invalid phone number: must be a non-empty string")
        
        # Remove whitespace
        phone = phone_number.strip()
        
        # Remove leading +
        if phone.startswith('+'):
            phone = phone[1:]
        
        # Convert 0 prefix to 234
        if phone.startswith('0'):
            phone = '234' + phone[1:]
        
        # Ensure it starts with 234 (Nigeria country code)
        if not phone.startswith('234'):
            raise TermiiSMSException(f"Invalid phone number: {phone_number} (country code 234 not found)")
        
        # Add back the +
        formatted_phone = '+' + phone
        
        # Validate format using regex
        pattern = PHONE_VALIDATION_PATTERNS.get('NG')
        if pattern and not re.match(pattern, formatted_phone):
            raise TermiiSMSException(f"Invalid Nigerian phone number format: {formatted_phone}")
        
        logger.debug(f"✅ Phone number formatted: {phone_number} → {formatted_phone}")
        return formatted_phone

    def check_sms_balance(self) -> Optional[float]:
        """
        Check remaining SMS balance on Termii account
        
        Returns:
            float: Remaining balance
        """
        try:
            endpoint = f"{self.base_url}/get-balance"
            params = {"api_key": self.api_key}
            
            response = requests.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            balance = data.get('balance')
            
            logger.info(f"💰 SMS Balance: {balance}")
            return balance
        
        except Exception as e:
            logger.error(f"❌ Failed to check SMS balance: {str(e)}")
            return None

    def get_message_length_info(self, message: str) -> Dict:
        """
        Get message length information (for SMS character counting)
        
        Args:
            message: SMS message content
            
        Returns:
            dict: Information about message length and parts
        """
        length = len(message)
        
        if length <= SMS_CHARACTER_LIMIT:
            parts = 1
            remaining_chars = SMS_CHARACTER_LIMIT - length
        else:
            # Multipart SMS
            parts = (length + SMS_CHARACTER_LIMIT - 1) // SMS_CHARACTER_LIMIT
            remaining_chars = (parts * SMS_CHARACTER_LIMIT) - length
        
        return {
            'length': length,
            'limit': SMS_CHARACTER_LIMIT,
            'parts': parts,
            'remaining_chars': remaining_chars,
            'is_multipart': parts > 1,
        }

    def validate_message(self, message: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SMS message
        
        Args:
            message: Message to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        if not message or not isinstance(message, str):
            return False, "Message must be a non-empty string"
        
        if len(message) > SMS_CHARACTER_LIMIT * 10:  # Allow up to 10 parts
            return False, f"Message too long (max {SMS_CHARACTER_LIMIT * 10} characters)"
        
        return True, None


# Singleton instance
_sms_service = None


def get_sms_service() -> TermiiSMSService:
    """Get or create SMS service singleton"""
    global _sms_service
    if _sms_service is None:
        _sms_service = TermiiSMSService()
    return _sms_service
