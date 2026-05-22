from django import views
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OffenceViewSet, OffenderViewSet, BookingViewSet, RegisterView, CitizenRegisterView, 
    AddVehicleView, VehiclesView, AdminDashboardStatsView, AdminOfficerManagementView, 
    PasswordResetRequestView, PasswordResetConfirmView, CitizenPasswordResetVerifyView,
    DriverInformationViewSet, SMSLogViewSet  # Phase 3: SMS API endpoints
)
from .views import paystack_webhook
from .views import get_paystack_config
from .views import verify_payment_by_reference

# 1. Create the router
router = DefaultRouter()

# 2. Register the URLs
router.register(r'offences', OffenceViewSet)
router.register(r'offenders', OffenderViewSet)
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'drivers', DriverInformationViewSet, basename='driver')  # Phase 3: Driver management
router.register(r'sms-logs', SMSLogViewSet, basename='sms-log')  # Phase 3: SMS log tracking


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
    path('admin/stats/', AdminDashboardStatsView.as_view(), name='admin-stats'),
    path('admin/officers/', AdminOfficerManagementView.as_view(), name='admin-officers-list'),
    path('admin/officers/<int:pk>/', AdminOfficerManagementView.as_view(), name='admin-officers-detail'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset-confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('citizen-password-reset/', CitizenPasswordResetVerifyView.as_view(), name='citizen_password_reset'),
]


