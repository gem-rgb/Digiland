# Migration 0028: Enable PostgreSQL Row-Level Security (RLS)
#
# This migration:
# 1. Creates a helper function set_tenant_id(uuid) to set app.current_tenant
# 2. Enables RLS on all tenant-scoped tables
# 3. Creates RLS policies enforcing tenant_id = current_setting('app.current_tenant')
# 4. Superusers bypass RLS (BYPASSRLS attribute)
#
# IMPORTANT: This migration is a no-op on SQLite (dev/test) and only
# executes RLS commands when the database vendor is PostgreSQL.

from django.db import migrations


# All tenant-scoped tables (Django model -> DB table name mapping)
TENANT_SCOPED_TABLES = [
    'core_agentrating',
    'core_agentkycapplication',
    'core_kycprofile',
    'core_landparcel',
    'core_transaction',
    'core_document',
    'core_supportticket',
    'core_message',
    'core_parcelview',
    'core_userfavorite',
    'core_jointbuyergroup',
    'core_jointbuyermember',
    'core_jointpaymentcontribution',
    'core_jointmemberremovalrequest',
    'core_platformlegaldocument',
    'core_landpromotion',
    'core_popupadcampaign',
    'core_popupadevent',
    'core_promotionanalyticslog',
    'core_searchquerylog',
    'core_buyerinterestprofile',
    'core_buyerengagementsignal',
    'core_promotiontier',
    'core_promotionplan',
    'core_promotionplanpayment',
    'core_sponsoredad',
    'core_adengagement',
    'core_adbillingevent',
    'core_analyticsevent',
    'core_recommendationlog',
    'core_fraudscore',
    'core_verificationbadge',
    'core_servicefee',
]


def enable_rls(apps, schema_editor):
    """Enable RLS on all tenant-scoped tables (PostgreSQL only)."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        # 1. Create the helper function to set tenant context
        cursor.execute("""
            CREATE OR REPLACE FUNCTION set_tenant_id(p_tenant_id UUID)
            RETURNS VOID AS $$
            BEGIN
                PERFORM set_config('app.current_tenant', COALESCE(p_tenant_id::TEXT, ''), FALSE);
            END;
            $$ LANGUAGE plpgsql;
        """)

        # 2. Create a function to clear tenant context
        cursor.execute("""
            CREATE OR REPLACE FUNCTION clear_tenant_id()
            RETURNS VOID AS $$
            BEGIN
                PERFORM set_config('app.current_tenant', '', FALSE);
            END;
            $$ LANGUAGE plpgsql;
        """)

        # 3. Enable RLS and create policies for each tenant-scoped table
        for table in TENANT_SCOPED_TABLES:
            # Check table exists before proceeding
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                [table]
            )
            if not cursor.fetchone()[0]:
                continue

            # Enable RLS on the table
            cursor.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;')

            # Force RLS even for table owners (superusers still bypass)
            cursor.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY;')

            # Drop existing policy if it exists (idempotent migration)
            cursor.execute(
                f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};"
            )

            # Create the RLS policy:
            # - When app.current_tenant is set, filter by tenant_id
            # - When app.current_tenant is empty (no tenant context), allow all rows
            #   (this supports admin/superuser access and background tasks)
            # - Superusers with BYPASSRLS always skip RLS entirely
            cursor.execute(f"""
                CREATE POLICY tenant_isolation_policy ON {table}
                USING (
                    current_setting('app.current_tenant', TRUE) = ''
                    OR
                    current_setting('app.current_tenant', TRUE) IS NULL
                    OR
                    tenant_id::TEXT = current_setting('app.current_tenant', TRUE)
                    OR
                    tenant_id IS NULL
                )
                WITH CHECK (
                    current_setting('app.current_tenant', TRUE) = ''
                    OR
                    current_setting('app.current_tenant', TRUE) IS NULL
                    OR
                    tenant_id::TEXT = current_setting('app.current_tenant', TRUE)
                    OR
                    tenant_id IS NULL
                );
            """)

        # 4. Grant usage on the helper functions to the application role
        cursor.execute("GRANT EXECUTE ON FUNCTION set_tenant_id(UUID) TO PUBLIC;")
        cursor.execute("GRANT EXECUTE ON FUNCTION clear_tenant_id() TO PUBLIC;")


def disable_rls(apps, schema_editor):
    """Disable RLS on all tenant-scoped tables (PostgreSQL only)."""
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        for table in TENANT_SCOPED_TABLES:
            # Check table exists
            cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                [table]
            )
            if not cursor.fetchone()[0]:
                continue

            # Drop the policy
            cursor.execute(
                f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};"
            )

            # Disable RLS
            cursor.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;')
            cursor.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;')

        # Drop helper functions
        cursor.execute("DROP FUNCTION IF EXISTS set_tenant_id(UUID);")
        cursor.execute("DROP FUNCTION IF EXISTS clear_tenant_id();")


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_add_tenant_id_and_audit_fields'),
    ]

    operations = [
        migrations.RunPython(enable_rls, disable_rls),
    ]
