from django import views
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OffenceViewSet, OffenderViewSet, BookingViewSet, RegisterView, CitizenRegisterView, AddVehicleView, VehiclesView
from .views import paystack_webhook
from .views import get_paystack_config
from .views import verify_payment_by_reference

# 1. Create the router
router = DefaultRouter()

# 2. Register the URLs
router.register(r'offences', OffenceViewSet)
router.register(r'offenders', OffenderViewSet)
router.register(r'bookings', BookingViewSet, basename='booking')


# 3. Expose the URLs to Django
urlpatterns = [
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('citizen-register/', CitizenRegisterView.as_view(), name='citizen-register'),
    path('vehicles/add/', AddVehicleView.as_view(), name='add-vehicle'),
    path('vehicles/', VehiclesView.as_view(), name='vehicles'),
    path('payments/webhook/paystack/', paystack_webhook, name='paystack-webhook'),
    path('payments/config/', get_paystack_config, name='paystack-config'),
    path('payments/verify/', verify_payment_by_reference, name='paystack-verify-by-ref'),
]
