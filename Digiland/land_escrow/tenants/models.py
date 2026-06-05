"""
Multi-tenant data models for Digiland.

Every tenant-scoped row in the database carries a `tenant_id` column that
identifies the owning Organization.  PostgreSQL Row-Level Security (RLS)
policies enforce isolation at the database level — even a raw SQL query
cannot cross tenant boundaries unless the superuser explicitly bypasses RLS.
"""
import uuid
from django.db import models
from django.conf import settings


class Organization(models.Model):
    """Represents a tenant organization in the multi-tenant system."""

    ORG_TYPE_CHOICES = [
        ('solo', 'Solo Agent'),
        ('agency', 'Real Estate Agency'),
        ('corporate', 'Corporate/Enterprise'),
        ('government', 'Government Body'),
    ]
    SUBSCRIPTION_CHOICES = [
        ('free', 'Free Tier'),
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, db_index=True)
    schema_name = models.CharField(max_length=63, unique=True, db_index=True,
                                   help_text='PostgreSQL schema name for data isolation')
    domain = models.CharField(max_length=253, unique=True, db_index=True, null=True, blank=True,
                              help_text='Custom domain for the organization')
    org_type = models.CharField(max_length=20, choices=ORG_TYPE_CHOICES, default='solo')
    subscription_tier = models.CharField(max_length=20, choices=SUBSCRIPTION_CHOICES, default='free')

    is_active = models.BooleanField(default=True, db_index=True)
    max_users = models.PositiveIntegerField(default=5)
    max_parcels = models.PositiveIntegerField(default=50)

    org_settings = models.JSONField(default=dict, blank=True, help_text='Organization-level settings')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_organizations'
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug'], name='idx_org_slug'),
            models.Index(fields=['domain'], name='idx_org_domain'),
            models.Index(fields=['is_active'], name='idx_org_active'),
            models.Index(fields=['schema_name'], name='idx_org_schema'),
            models.Index(fields=['subscription_tier'], name='idx_org_sub_tier'),
        ]

    def __str__(self):
        return self.name


class OrganizationMembership(models.Model):
    """Links users to organizations with role-based access."""

    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('member', 'Member'),
        ('viewer', 'Viewer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='org_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    is_default = models.BooleanField(default=False,
                                     help_text='Is this the user\'s default/active organization?')

    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_org_invitations'
    )

    class Meta:
        unique_together = ('organization', 'user')
        ordering = ['-joined_at']
        indexes = [
            models.Index(fields=['user', 'is_default'], name='idx_membership_user_default'),
            models.Index(fields=['organization', 'role'], name='idx_membership_org_role'),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.organization.name} ({self.role})"


class TenantModelMixin(models.Model):
    """
    Abstract base model that adds `tenant_id` to every row.

    All tenant-scoped models MUST inherit from this mixin so that every row
    can tell which organization it belongs to.  PostgreSQL Row-Level Security
    policies use this column to enforce isolation at the database level,
    independent of application code.
    """
    tenant_id = models.UUIDField(
        db_index=True, null=True, blank=True,
        help_text='Organization tenant ID for row-level security isolation'
    )

    class Meta:
        abstract = True
