from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import User, Offence, Offender, Booking, Vehicle, Payment, DriverInformation, SMSLog
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
        from .models import Offender, Vehicle
        offender, created= Offender.objects.get_or_create(
            driver_license_number=validated_data['username'],
            defaults={
                'driver_name': f"{validated_data['first_name']} {validated_data['last_name']}"
            }
        )

        # 3. Create the Vehicle and link it to the Driver!
        Vehicle.objects.get_or_create(
            plate_number=validated_data['plate_number'],
            defaults={
                'owner': offender # This links the car to the driver!
            }
        )
        
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