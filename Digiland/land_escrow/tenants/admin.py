from django.contrib import admin
from .models import Organization, OrganizationMembership


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'org_type', 'subscription_tier', 'is_active', 'created_at')
    list_filter = ('org_type', 'subscription_tier', 'is_active')
    search_fields = ('name', 'slug', 'domain')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'role', 'is_default', 'joined_at')
    list_filter = ('role', 'is_default')
    search_fields = ('user__email', 'organization__name')
    readonly_fields = ('id', 'joined_at')
    ordering = ('-joined_at',)
