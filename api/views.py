from django.contrib.auth import get_user_model
User = get_user_model()
from django.db.models import Sum, Q
import random
import string
from rest_framework import generics, permissions
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from .models import Offence, Offender, Booking, User, Vehicle
from .serializers import OffenceSerializer, OffenderSerializer, BookingSerializer, RegisterSerializer, CitizenRegisterSerializer, CustomTokenObtainPairSerializer, VehicleSerializer, PaymentSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
import os
import requests
import hmac
import hashlib
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

def generate_reference_id():
    # string.ascii_uppercase gives us 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    # string.digits gives us '0123456789'
    # We combine them into one giant bucket of characters
    allowed_chars = string.ascii_uppercase + string.digits
    
    # random.choices picks 6 random characters from that bucket
    random_part = ''.join(random.choices(allowed_chars, k=6))
    
    # We return the final formatted string using an f-string
    return f"OYR-{random_part}"

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission: Anyone can view the list of offences,
    but only Superusers (Admins) can add, edit, or delete them.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS: # GET requests
            return True
        return request.user and request.user.is_superuser # POST, PUT, PATCH, DELETE

class OffenceViewSet(viewsets.ModelViewSet):
    
    from .models import Offence
    from .serializers import OffenceSerializer
    
    queryset = Offence.objects.all().order_by('name')
    serializer_class = OffenceSerializer
    permission_classes = [IsAdminOrReadOnly]

class OffenderViewSet(viewsets.ModelViewSet):
    queryset = Offender.objects.all()
    serializer_class = OffenderSerializer

class BookingViewSet(viewsets.ModelViewSet):
    serializer_class = BookingSerializer

   
    def get_queryset(self):
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            # Show the master list of all tickets across the state
            return Booking.objects.all().order_by('-date_time')
        # Offenders are linked to User accounts by driver_license_number == User.username
        return Booking.objects.filter(offender__driver_license_number=user.username).order_by('-date_time')
            
    def perform_update(self, serializer):
        user = self.request.user
        ticket = serializer.instance
        
        # If someone is trying to change the payment_status...
        if 'payment_status' in self.request.data:
            new_status = self.request.data.get('payment_status')
            # ...and they are NOT an officer/admin
            if not user.is_staff and not user.is_superuser:
                # Allow the offender themselves to mark their ticket as Paid (so citizens can pay via frontend)
                # Offender is linked by driver_license_number == user.username
                if not (ticket.offender and ticket.offender.driver_license_number == user.username and new_status == 'Paid'):
                    # Kick them out with a 403 Forbidden error!
                    raise PermissionDenied("Security Alert: Citizens cannot manually change ticket payment statuses.")
            if user.is_staff and not user.is_superuser:
                if ticket.officer != user:
                    raise PermissionDenied("Accountability Alert: You can only clear tickets that you personally issued.")
        
        # Otherwise, save the update normally
        serializer.save()

        # If the booking was just marked Paid, create a Payment record if one doesn't exist
        try:
            from .models import Payment
            if 'payment_status' in self.request.data and self.request.data.get('payment_status') == 'Paid':
                # create a payment record if none exists for this booking
                if not Payment.objects.filter(booking=ticket).exists():
                    Payment.objects.create(booking=ticket, amount=ticket.amount_due, transaction_id=self.request.data.get('transaction_id'))
        except Exception:
            # If anything goes wrong here, don't block the update; just log to stdout for now
            import traceback
            traceback.print_exc()
  
    def perform_create(self, serializer):
        
        new_ref_id = generate_reference_id()
        selected_offence = serializer.validated_data.get('offence')
        calculated_fine = selected_offence.fine_amount
        
       
        serializer.save(
            reference_id=new_ref_id, 
            amount_due=calculated_fine,
            officer=self.request.user  
        )

    @action(detail=True, methods=['post'], url_path='pay')
    def pay(self, request, pk=None):
        booking = self.get_object()

        # Only allow officers or admins to register payments via this endpoint
        user = request.user
        if not user.is_staff and not user.is_superuser and not user.is_officer:
            return Response({'detail': 'Only officers or admins can register payments.'}, status=status.HTTP_403_FORBIDDEN)

        amount = booking.amount_due

        # Create a Payment record (transaction_id would come from a payment gateway)
        payment_data = {
            'booking': booking.id,
            'amount': amount,
            'transaction_id': request.data.get('transaction_id', None)
        }
        serializer = PaymentSerializer(data=payment_data)
        if serializer.is_valid():
            serializer.save()
            booking.payment_status = 'Paid'
            booking.save(update_fields=['payment_status'])
            return Response({'detail': 'Payment recorded and booking marked as Paid.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='verify-payment')
    def verify_payment(self, request, pk=None):
        """Verify a payment reference with Paystack and mark booking paid if valid.

        Body: { "reference": "PSK_REF_123" }
        """
        booking = self.get_object()
        ref = request.data.get('reference')
        print(f"\n🔍 [verify_payment] Called for booking {pk} with reference: {ref}")
        
        if not ref:
            print(f"❌ [verify_payment] No reference provided")
            return Response({'detail': 'reference is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Support multiple possible .env key names (some deployments use *_KEY suffix)
        paystack_secret = os.getenv('PAYSTACK_SECRET') or os.getenv('PAYSTACK_SECRET_KEY') or os.getenv('PAYSTACK_SK')
        if not paystack_secret:
            print(f"❌ [verify_payment] Paystack secret not configured")
            return Response({'detail': 'Paystack secret not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Call Paystack verify endpoint
        print(f"📤 [verify_payment] Calling Paystack API for reference: {ref}")
        try:
            resp = requests.get(f'https://api.paystack.co/transaction/verify/{ref}', headers={'Authorization': f'Bearer {paystack_secret}'}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            print(f"✅ [verify_payment] Paystack response: {data}")
        except Exception as e:
            print(f"❌ [verify_payment] Paystack API failed: {str(e)}")
            return Response({'detail': f'Failed to verify with Paystack: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)

        if not data.get('status') or not data.get('data'):
            print(f"❌ [verify_payment] Invalid response from Paystack: {data}")
            return Response({'detail': 'Invalid response from Paystack'}, status=status.HTTP_502_BAD_GATEWAY)

        pay_data = data['data']
        # Paystack returns amount in kobo (lowest currency unit)
        paid_amount = pay_data.get('amount') / 100.0 if pay_data.get('amount') is not None else None
        status_str = pay_data.get('status')
        print(f"💰 [verify_payment] Paystack status: {status_str}, amount: {paid_amount}")

        if status_str != 'success':
            print(f"❌ [verify_payment] Payment not successful: {status_str}")
            return Response({'detail': f'Payment not successful: {status_str}'}, status=status.HTTP_400_BAD_REQUEST)

        # Optional: ensure amount matches
        if paid_amount is not None and float(paid_amount) < float(booking.amount_due):
            print(f"❌ [verify_payment] Paid amount ({paid_amount}) < booking amount ({booking.amount_due})")
            return Response({'detail': 'Paid amount is less than booking amount'}, status=status.HTTP_400_BAD_REQUEST)

        # Record payment and mark booking paid
        from .models import Payment
        print(f"💾 [verify_payment] Updating booking {booking.id} to Paid status...")
        # Ensure the payment creation and booking update are atomic to avoid race conditions
        with transaction.atomic():
            payment, created = Payment.objects.get_or_create(booking=booking, transaction_id=ref, defaults={'amount': booking.amount_due})
            booking.payment_status = 'Paid'
            booking.save(update_fields=['payment_status'])
            print(f"✅ [verify_payment] Payment record {'created' if created else 'updated'}: {payment.id}")
            print(f"✅ [verify_payment] Booking {booking.id} marked as Paid")
        return Response({'detail': 'Payment verified and booking marked as Paid.'})


# Paystack webhook receiver
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def paystack_webhook(request):
    """Handle Paystack webhooks. Validates signature and updates booking/payment state.

    Paystack sends x-paystack-signature header which is HMAC SHA512 of the request.body using PAYSTACK_SECRET.
    """
    # Support multiple possible .env key names
    paystack_secret = os.getenv('PAYSTACK_SECRET') or os.getenv('PAYSTACK_SECRET_KEY') or os.getenv('PAYSTACK_SK')
    if not paystack_secret:
        return Response({'detail': 'Paystack secret not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    signature = request.headers.get('x-paystack-signature')
    raw_body = request.body
    computed = hmac.new(paystack_secret.encode('utf-8'), raw_body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(computed, signature or ''):
        return Response({'detail': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

    payload = request.data
    # handle payment.success event
    event = payload.get('event')
    data = payload.get('data', {})
    if data and data.get('status') == 'success':
        reference = data.get('reference')
        # verify server-side similarly to ensure idempotency
        try:
            resp = requests.get(f'https://api.paystack.co/transaction/verify/{reference}', headers={'Authorization': f'Bearer {paystack_secret}'}, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            if result.get('status') and result['data'].get('status') == 'success':
                # Try to find booking by reference id present in metadata or map via transaction reference
                # If you previously stored transaction_id on Payment, use that. We'll try booking with matching reference_id first.
                reference_id = data.get('metadata', {}).get('reference_id') or None
                from .models import Booking, Payment
                booking = None
                if reference_id:
                    booking = Booking.objects.filter(reference_id=reference_id).first()
                if not booking:
                    # try to find payment with transaction_id
                    payment = Payment.objects.filter(transaction_id=reference).first()
                    if payment:
                        booking = payment.booking

                if booking:
                    # Use atomic block to ensure idempotent safe write
                    from .models import Payment
                    with transaction.atomic():
                        Payment.objects.get_or_create(booking=booking, transaction_id=reference, defaults={'amount': booking.amount_due})
                        booking.payment_status = 'Paid'
                        booking.save(update_fields=['payment_status'])
        except Exception:
            pass

    return Response({'status': 'ok'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_paystack_config(request):
    """Return public Paystack configuration for frontend (public key)."""
    # Support multiple possible .env key names for public key
    public = os.getenv('PAYSTACK_PUBLIC') or os.getenv('PAYSTACK_PUBLIC_KEY') or os.getenv('PAYSTACK_PK')
    if not public:
        return Response({'detail': 'Paystack public key not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response({'publicKey': public})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment_by_reference(request):
    """Verify a Paystack transaction by reference and mark the related booking Paid.

    Body: { "reference": "PSK_REF_123" }
    This endpoint will:
      - call Paystack verify API
      - read metadata.reference_id from Paystack response
      - find booking by reference_id (or by existing Payment.transaction_id)
      - create Payment record and mark booking Paid
    """
    ref = request.data.get('reference')
    if not ref:
        return Response({'detail': 'reference is required'}, status=status.HTTP_400_BAD_REQUEST)

    paystack_secret = os.getenv('PAYSTACK_SECRET') or os.getenv('PAYSTACK_SECRET_KEY') or os.getenv('PAYSTACK_SK')
    if not paystack_secret:
        return Response({'detail': 'Paystack secret not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        resp = requests.get(f'https://api.paystack.co/transaction/verify/{ref}', headers={'Authorization': f'Bearer {paystack_secret}'}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return Response({'detail': f'Failed to verify with Paystack: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)

    if not data.get('status') or not data.get('data'):
        return Response({'detail': 'Invalid response from Paystack'}, status=status.HTTP_502_BAD_GATEWAY)

    pay_data = data['data']
    status_str = pay_data.get('status')
    paid_amount = pay_data.get('amount') / 100.0 if pay_data.get('amount') is not None else None

    if status_str != 'success':
        return Response({'detail': f'Payment not successful: {status_str}'}, status=status.HTTP_400_BAD_REQUEST)

    # Try to locate booking using metadata.reference_id or existing Payment
    reference_id = pay_data.get('metadata', {}).get('reference_id') or None
    from .models import Booking, Payment
    booking = None
    if reference_id:
        booking = Booking.objects.filter(reference_id=reference_id).first()

    if not booking:
        payment = Payment.objects.filter(transaction_id=ref).first()
        if payment:
            booking = payment.booking

    if not booking:
        return Response({'detail': 'Could not locate booking for this transaction reference'}, status=status.HTTP_404_NOT_FOUND)

    # Check amount
    if paid_amount is not None and float(paid_amount) < float(booking.amount_due):
        return Response({'detail': 'Paid amount is less than booking amount'}, status=status.HTTP_400_BAD_REQUEST)

    payment, created = Payment.objects.get_or_create(booking=booking, transaction_id=ref, defaults={'amount': booking.amount_due})
    with transaction.atomic():
        payment, created = Payment.objects.get_or_create(booking=booking, transaction_id=ref, defaults={'amount': booking.amount_due})
        booking.payment_status = 'Paid'
        booking.save(update_fields=['payment_status'])
    return Response({'detail': 'Payment verified and booking marked as Paid.'})

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,) 
    serializer_class = RegisterSerializer



class CitizenRegisterView(generics.CreateAPIView):
    permission_classes = (AllowAny,) 
    serializer_class = CitizenRegisterSerializer

class AddVehicleView(generics.CreateAPIView):
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated] 

    def perform_create(self, serializer):
        #Look up the Driver Profile (Offender) using the logged-in user's username
        current_driver = Offender.objects.get(driver_license_number=self.request.user.username)
        
        # Save the new vehicle and automatically set the owner to this driver
        serializer.save(owner=current_driver)

class VehiclesView(generics.ListAPIView):
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Look up the logged-in user and only return THEIR cars
        return Vehicle.objects.filter(owner__driver_license_number=self.request.user.username)


class AdminDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Enforce strict RBAC: Only superusers/admins can access this
        if not request.user.is_superuser:
            raise PermissionDenied("Security Alert: Only administrators can view state statistics.")

        # Calculate revenue metrics
        total_revenue = Booking.objects.filter(payment_status='Paid').aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        pending_revenue = Booking.objects.filter(payment_status='Pending').aggregate(Sum('amount_due'))['amount_due__sum'] or 0
        
        # Calculate operational metrics
        total_tickets = Booking.objects.count()
        # Assuming officers are marked as 'is_staff' in your User model
        active_officers = User.objects.filter(is_staff=True, is_superuser=False).count()

        return Response({
            'total_revenue': total_revenue,
            'pending_revenue': pending_revenue,
            'total_tickets': total_tickets,
            'active_officers': active_officers
        })

class AdminOfficerManagementView(APIView):
    permission_classes = [IsAuthenticated]

    # --- 1. FETCH OFFICERS (Your perfectly updated code) ---
    def get(self, request, pk=None):
        if not request.user.is_superuser:
            raise PermissionDenied("Security Alert: Only admins can view officers.")
        
        User = get_user_model()
        from .models import Offender 
        
        citizen_usernames = Offender.objects.exclude(
            driver_license_number__isnull=True
        ).exclude(
            driver_license_number__exact=''
        ).values_list('driver_license_number', flat=True)
        
        users = User.objects.filter(
            Q(is_staff=True) | ~Q(username__in=citizen_usernames),
            is_superuser=False
        ).order_by('-date_joined').values(
            'id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined'
        )
        
        return Response(list(users))

    # --- 2. APPROVE OFFICER & UNLOCK ACCOUNT ---
    def patch(self, request, pk=None):
        if not request.user.is_superuser:
            raise PermissionDenied("Security Alert: Only admins can approve officers.")
        
        User = get_user_model()
        try:
            user = User.objects.get(pk=pk)
            
            # Grant the system badge
            user.is_staff = True  
            # Mark as official officer role
            user.is_officer = True 
            # Unlock the account (overriding the is_active=False from the serializer)
            user.is_active = True 
            
            user.save()
            return Response({"message": "Officer approved and account unlocked successfully!"})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

    # --- 3. REJECT / DELETE OFFICER ---
    def delete(self, request, pk=None):
        if not request.user.is_superuser:
            raise PermissionDenied("Security Alert: Only admins can remove officers.")
        
        User = get_user_model()
        try:
            user = User.objects.get(pk=pk)
            user.delete() 
            return Response({"message": "User removed successfully!"})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)