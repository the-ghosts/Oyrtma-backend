from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, Offence, Offender, Booking, Vehicle, DriverInformation, SMSLog


admin.site.register(User, UserAdmin)

# Register our traffic system models
admin.site.register(Offence)
admin.site.register(Offender)
admin.site.register(Booking)
admin.site.register(Vehicle)


@admin.register(DriverInformation)
class DriverInformationAdmin(admin.ModelAdmin):
    """
    Admin interface for managing driver information and vehicle data.
    """
    list_display = ['plate_number', 'driver_name', 'phone_number_masked', 'state', 'vehicle_type', 'is_active_badge', 'created_at']
    list_filter = ['state', 'is_active', 'created_at', 'vehicle_type']
    search_fields = ['plate_number', 'phone_number', 'driver_name', 'state']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Vehicle Information', {
            'fields': ('plate_number', 'vehicle_type')
        }),
        ('Driver Details', {
            'fields': ('driver_name', 'phone_number', 'email', 'license_number')
        }),
        ('Location & Status', {
            'fields': ('state', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def phone_number_masked(self, obj):
        """Display masked phone number for privacy"""
        if obj.phone_number:
            return f"{obj.phone_number[:8]}****{obj.phone_number[-3:]}"
        return "-"
    phone_number_masked.short_description = 'Phone Number'
    
    def is_active_badge(self, obj):
        """Display active status as colored badge"""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 8px; border-radius: 3px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    actions = ['activate_drivers', 'deactivate_drivers']
    
    def activate_drivers(self, request, queryset):
        """Bulk action to activate drivers"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} driver(s) activated.')
    activate_drivers.short_description = "Activate selected drivers"
    
    def deactivate_drivers(self, request, queryset):
        """Bulk action to deactivate drivers"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} driver(s) deactivated.')
    deactivate_drivers.short_description = "Deactivate selected drivers"


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    """
    Admin interface for monitoring SMS logs and notifications.
    """
    list_display = ['phone_number_masked', 'status_badge', 'booking_ref', 'sent_at', 'created_at']
    list_filter = ['status', 'created_at', 'sent_at']
    search_fields = ['phone_number', 'message', 'booking__reference_id']
    readonly_fields = ['created_at', 'booking', 'driver_info', 'phone_number', 'message', 'termii_response', 'error_message', 'sent_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Message Details', {
            'fields': ('phone_number', 'message', 'status')
        }),
        ('Related Records', {
            'fields': ('booking', 'driver_info')
        }),
        ('Termii Response', {
            'fields': ('termii_response', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'sent_at'),
            'classes': ('collapse',)
        }),
    )
    
    def phone_number_masked(self, obj):
        """Display masked phone number for privacy"""
        if obj.phone_number:
            return f"{obj.phone_number[:8]}****{obj.phone_number[-3:]}"
        return "-"
    phone_number_masked.short_description = 'Phone Number'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#ffc107',
            'sent': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display().upper()
        )
    status_badge.short_description = 'Status'
    
    def booking_ref(self, obj):
        """Display booking reference"""
        if obj.booking:
            return obj.booking.reference_id
        return "-"
    booking_ref.short_description = 'Booking Reference'
    
    actions = ['retry_failed_sms']
    
    def retry_failed_sms(self, request, queryset):
        """Bulk action to retry failed SMS"""
        failed = queryset.filter(status='failed').count()
        queryset.filter(status='failed').update(status='pending')
        self.message_user(request, f'{failed} failed SMS marked for retry.')
    retry_failed_sms.short_description = "Retry failed SMS"