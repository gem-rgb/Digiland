# Generated migration for auth models

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_promotion_ads_analytics_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserMFA',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('totp_secret', models.CharField(blank=True, default='', max_length=64)),
                ('is_enabled', models.BooleanField(db_index=True, default=False)),
                ('setup_started_at', models.DateTimeField(blank=True, null=True)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('recovery_codes', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mfa_config', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['user', 'is_enabled'], name='idx_mfa_user_enabled')],
            },
        ),
        migrations.CreateModel(
            name='TrustedDevice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('trust_token', models.CharField(db_index=True, max_length=128)),
                ('device_name', models.CharField(default='Unknown Device', max_length=200)),
                ('device_type', models.CharField(default='unknown', max_length=50)),
                ('user_agent', models.TextField(blank=True, default='')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trusted_devices', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['user', 'trust_token'], name='idx_device_user_token'),
                    models.Index(fields=['user', 'expires_at'], name='idx_device_user_expires'),
                ],
            },
        ),
        migrations.CreateModel(
            name='UserSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session_key', models.CharField(db_index=True, max_length=128)),
                ('refresh_token_jti', models.CharField(blank=True, db_index=True, default='', max_length=128)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, default='')),
                ('device_type', models.CharField(blank=True, default='', max_length=50)),
                ('location', models.CharField(blank=True, default='', max_length=200)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-last_activity'],
                'indexes': [
                    models.Index(fields=['user', 'is_active'], name='idx_session_user_active'),
                    models.Index(fields=['refresh_token_jti'], name='idx_session_jti'),
                    models.Index(fields=['user', 'is_active', 'last_activity'], name='idx_session_user_activity'),
                ],
            },
        ),
        migrations.CreateModel(
            name='OAuthProvider',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('provider', models.CharField(choices=[('google', 'Google'), ('github', 'GitHub'), ('microsoft', 'Microsoft'), ('oidc', 'OpenID Connect'), ('saml', 'SAML')], db_index=True, max_length=20)),
                ('client_id', models.CharField(max_length=500)),
                ('client_secret', models.TextField()),
                ('authorization_url', models.URLField()),
                ('token_url', models.URLField()),
                ('userinfo_url', models.URLField(blank=True, default='')),
                ('scope', models.CharField(default='openid email profile', max_length=200)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('config', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'indexes': [models.Index(fields=['provider', 'is_active'], name='idx_oauth_provider_active')],
            },
        ),
        migrations.CreateModel(
            name='OAuthAccount',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider_user_id', models.CharField(db_index=True, max_length=255)),
                ('email', models.EmailField(blank=True, default='', max_length=254)),
                ('access_token', models.TextField(blank=True, default='')),
                ('refresh_token', models.TextField(blank=True, default='')),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('profile_data', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accounts', to='core.oauthprovider')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='oauth_accounts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('provider', 'provider_user_id')},
                'indexes': [
                    models.Index(fields=['user', 'provider'], name='idx_oauth_user_provider'),
                    models.Index(fields=['provider', 'provider_user_id'], name='idx_oauth_provider_uid'),
                ],
            },
        ),
        migrations.CreateModel(
            name='Permission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('codename', models.CharField(db_index=True, max_length=100, unique=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('resource_type', models.CharField(db_index=True, max_length=50)),
                ('action', models.CharField(max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['resource_type', 'action'],
                'indexes': [models.Index(fields=['resource_type', 'action'], name='idx_perm_resource_action')],
            },
        ),
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('role', models.CharField(db_index=True, max_length=20)),
                ('conditions', models.JSONField(blank=True, default=dict, help_text='ABAC conditions for this role-permission mapping')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_assignments', to='core.permission')),
            ],
            options={
                'unique_together': {('role', 'permission')},
                'indexes': [models.Index(fields=['role'], name='idx_roleperm_role')],
            },
        ),
        migrations.CreateModel(
            name='LoginAttempt',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('ip_address', models.GenericIPAddressField(db_index=True)),
                ('user_agent', models.TextField(blank=True, default='')),
                ('success', models.BooleanField(default=False)),
                ('failure_reason', models.CharField(blank=True, default='', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['email', 'success', 'created_at'], name='idx_login_email_success'),
                    models.Index(fields=['ip_address', 'success', 'created_at'], name='idx_login_ip_success'),
                ],
            },
        ),
    ]
