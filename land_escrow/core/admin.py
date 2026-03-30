from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, LandParcel, Transaction, Document, AuditLog, SupportTicket, Message

class CustomUserAdmin(UserAdmin):
    # Specify the fields that should be displayed in the list view
    list_display = ('email', 'role', 'id_number', 'is_identity_verified', 'is_staff')
    search_fields = ('email', 'id_number')
    ordering = ('email',)
    
    # Define custom fieldsets to ensure the Admin can toggle high-security fields natively
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('id_number', 'phone_number')}),
        ('Security & Fencing', {'fields': ('role', 'is_identity_verified', 'gavakonect_verification_id')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Define add_fieldsets since AbstractUser handles creation differently
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'role', 'id_number', 'phone_number', 'is_identity_verified'),
        }),
    )

# Register the models to the secure Offline Admin Vault
admin.site.register(User, CustomUserAdmin)
admin.site.register(LandParcel)
admin.site.register(Transaction)
admin.site.register(Document)
admin.site.register(AuditLog)
admin.site.register(SupportTicket)
admin.site.register(Message)
