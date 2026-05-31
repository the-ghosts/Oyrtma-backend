from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import User, Offence, Offender, Booking, Vehicle, Payment, DriverInformation, SMSLog, TicketDispute
from django.db import IntegrityError
from django.contrib.auth import get_user_model
User = get_user_model()

class OffenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offence
        fields = '__all__'

class OffenderSerializer(serializers.ModelSerializer):
    
    plate_number = serializers.CharField(write_only=True, required=True)
    registered_vehicles = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Offender
       
        fields = ['id', 'driver_license_number', 'driver_name', 'email', 'phone_number', 'plate_number', 'registered_vehicles']
    
    def get_registered_vehicles(self, obj):
        return [vehicle.plate_number for vehicle in obj.vehicles.all()]

    def create(self, validated_data):
        plate_number = validated_data.pop('plate_number', None)

        # Try to reuse an existing Offender when the driver_license_number is provided
        try:
            driver_license = validated_data.get('driver_license_number')
            if driver_license:
                offender, created = Offender.objects.get_or_create(
                    driver_license_number=driver_license,
                    defaults={
                        'driver_name': validated_data.get('driver_name'),
                        'email': validated_data.get('email'),
                        'phone_number': validated_data.get('phone_number')
                    }
                )
            else:
                offender = Offender.objects.create(**validated_data)
        except IntegrityError as e:
            # Return a validation error instead of causing a 500 response
            raise serializers.ValidationError({'non_field_errors': ['Offender with provided identifier already exists.']})

        if plate_number:
            vehicle, v_created = Vehicle.objects.get_or_create(
                plate_number=plate_number,
                defaults={'owner': offender}
            )
            # If the vehicle already exists but has no owner, assign it to this offender
            if vehicle.owner_id is None:
                vehicle.owner = offender
                vehicle.save(update_fields=['owner'])

        return offender

class BookingSerializer(serializers.ModelSerializer):
    officer_name = serializers.SerializerMethodField()
    officer = serializers.SerializerMethodField()
    plate_number = serializers.ReadOnlyField()
    offender_license = serializers.CharField(source='offender.driver_license_number', read_only=True)

    offence_name = serializers.CharField(source='offence.name', read_only=True)
    offence_description = serializers.CharField(source='offence.description', read_only=True)
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields= ['reference_id', 'amount_due', 'date_time']
        

    def get_officer_name(self, obj):
        if obj.officer:
            # Prefer full name if available, otherwise username
            full_name = obj.officer.get_full_name()
            if full_name:
                return full_name
            return getattr(obj.officer, 'username', 'Unknown Officer')
        return "System Generated"

    def get_officer(self, obj):
        """Return a small structured object for the officer (or None).

        Example: { 'id': 3, 'username': 'jdoe', 'full_name': 'John Doe' }
        """
        if not obj.officer:
            return None

        user = obj.officer
        return {
            'id': getattr(user, 'id', None),
            'username': getattr(user, 'username', None),
            'full_name': user.get_full_name() or getattr(user, 'username', None),
        }


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'booking', 'amount', 'transaction_id', 'paid_at']

class RegisterSerializer(serializers.Serializer):
    
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()

    def create(self, validated_data):
      
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            email=validated_data['email']
        )
        
        
        user.is_active = False
        user.save()
        
        return user

class CitizenRegisterSerializer(serializers.Serializer):
    # 2. ADD THE UNIQUE VALIDATOR TO CATCH DUPLICATES GRACEFULLY
    username = serializers.CharField(
        max_length=150,
        validators=[UniqueValidator(queryset=User.objects.all())] 
    ) 
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    plate_number = serializers.CharField(max_length=20, write_only=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, write_only=True)

    def create(self, validated_data):
        # 1. Create the Authentication Account
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name']
        )
        user.is_active = True
        user.save()

        # 2. Create the Driver Profile (Offender)
        from .models import Offender, Vehicle, DriverInformation
        phone_number = validated_data.get('phone_number', '')

        offender, created = Offender.objects.get_or_create(
            driver_license_number=validated_data['username'],
            defaults={
                'driver_name': f"{validated_data['first_name']} {validated_data['last_name']}",
                'phone_number': phone_number
            }
        )
        if not created and phone_number:
            offender.phone_number = phone_number
            offender.save(update_fields=['phone_number'])

        plate_number = validated_data['plate_number'].strip().upper()

        # 3. Create or Update Driver Registry (DriverInformation)
        driver_info, di_created = DriverInformation.objects.get_or_create(
            plate_number=plate_number,
            defaults={
                'phone_number': phone_number,
                'driver_name': offender.driver_name,
                'state': 'Oyo',
                'license_number': offender.driver_license_number,
                'email': user.email or '',
                'vehicle_type': 'Unknown',
                'is_active': True
            }
        )
        if not di_created:
            # Sync DriverInformation if it already exists
            updated = False
            if not driver_info.is_active:
                driver_info.is_active = True
                updated = True
            if not driver_info.phone_number and phone_number:
                driver_info.phone_number = phone_number
                updated = True
            if not driver_info.driver_name or driver_info.driver_name == 'Unknown':
                driver_info.driver_name = offender.driver_name
                updated = True
            if not driver_info.license_number:
                driver_info.license_number = offender.driver_license_number
                updated = True
            if updated:
                driver_info.save()

        # Resolve vehicle model from registry if it exists
        vehicle_model = 'Unknown'
        if not di_created and driver_info.vehicle_type and driver_info.vehicle_type != 'Unknown':
            vehicle_model = driver_info.vehicle_type

        # 4. Create or Update the Vehicle and link it to the driver!
        vehicle, v_created = Vehicle.objects.get_or_create(
            plate_number=plate_number,
            defaults={
                'owner': offender,
                'vehicle_model': vehicle_model
            }
        )
        if not v_created:
            vehicle.owner = offender
            if vehicle_model and vehicle_model != 'Unknown':
                vehicle.vehicle_model = vehicle_model
            vehicle.save()
        
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        
        data = super().validate(attrs)

        from .models import Offender
        is_citizen = Offender.objects.filter(driver_license_number=self.user.username).exists()

        if is_citizen:
            data['user_role'] = 'Citizen'
        elif self.user.is_superuser:
            data['user_role'] = 'Admin'
        else:
            data['user_role'] = 'Officer'

        return data

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'plate_number', 'vehicle_model']


class DriverInformationSerializer(serializers.ModelSerializer):
    """
    Serializer for DriverInformation model.
    Used for SMS notification lookup and management.
    """
    class Meta:
        model = DriverInformation
        fields = [
            'id', 'plate_number', 'phone_number', 'driver_name', 
            'state', 'license_number', 'email', 'vehicle_type', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_phone_number(self, value):
        """Validate phone number format"""
        if not value.startswith('+234') and not value.startswith('0'):
            raise serializers.ValidationError(
                "Phone number must start with +234 or 0"
            )
        return value
    
    def validate_plate_number(self, value):
        """Validate plate number format"""
        if len(value) < 5:
            raise serializers.ValidationError(
                "Plate number must be at least 5 characters"
            )
        return value.upper()


class SMSLogSerializer(serializers.ModelSerializer):
    """
    Serializer for SMSLog model.
    Used for monitoring and auditing SMS notifications.
    """
    booking_reference = serializers.CharField(source='booking.reference_id', read_only=True)
    driver_name = serializers.CharField(source='driver_info.driver_name', read_only=True)
    
    class Meta:
        model = SMSLog
        fields = [
            'id', 'booking', 'booking_reference', 'driver_info', 'driver_name',
            'phone_number', 'message', 'status', 'termii_response', 
            'error_message', 'sent_at', 'created_at'
        ]
        read_only_fields = ['created_at', 'sent_at', 'termii_response', 'error_message']
    
    def to_representation(self, instance):
        """Mask phone number in response"""
        representation = super().to_representation(instance)
        if representation.get('phone_number'):
            phone = representation['phone_number']
            representation['phone_number'] = f"{phone[:8]}****{phone[-3:]}"
        return representation


class TicketDisputeSerializer(serializers.ModelSerializer):
    booking_reference = serializers.CharField(source='booking.reference_id', read_only=True)
    amount_due = serializers.DecimalField(source='booking.amount_due', max_digits=10, decimal_places=2, read_only=True)
    offence_name = serializers.CharField(source='booking.offence.name', read_only=True)
    citizen_name = serializers.CharField(source='offender.driver_name', read_only=True)
    plate_number = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TicketDispute
        fields = [
            'id', 'booking', 'booking_reference', 'amount_due', 'offence_name', 
            'citizen_name', 'plate_number', 'reason', 'description', 'status', 
            'submitted_at', 'reviewed_at', 'review_comments'
        ]
        read_only_fields = ['status', 'submitted_at', 'reviewed_at', 'review_comments']

    def get_plate_number(self, obj):
        return obj.booking.plate_number


class CitizenProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='driver_license_number', read_only=True)
    driver_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Offender
        fields = ['id', 'username', 'driver_name', 'driver_license_number', 'phone_number', 'email']


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_new_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters.")
        return value