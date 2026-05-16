from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Offence, Offender, Booking, Vehicle


admin.site.register(User, UserAdmin)

# Register our traffic system models
admin.site.register(Offence)
admin.site.register(Offender)
admin.site.register(Booking)
admin.site.register(Vehicle)