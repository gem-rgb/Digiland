# Migration 0030: Additional production indexes
#
# Adds standalone indexes for high-frequency filter columns that were only
# present in composite indexes (with tenant_id). Non-tenant-scoped queries
# such as admin dashboards and background jobs need single-column indexes
# for acceptable performance.
#
# Indexes added:
#   - Transaction.status       — admin dashboard & background job filtering
#   - Transaction.buyer        — buyer's transaction history (non-composite)
#   - Transaction.seller       — seller's transaction history (non-composite)
#   - Transaction.created_at   — chronological ordering / cleanup jobs
#   - LandParcel.verification_status — admin verification queue
#   - LandParcel.listed_by     — seller's parcel listing page
#   - LandParcel.created_at    — chronological listing & cleanup


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_production_indexes_and_email_verified'),
    ]

    operations = [
        # ── Transaction indexes ──────────────────────────────────────────
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['status'], name='idx_transaction_status'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['buyer'], name='idx_transaction_buyer'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['seller'], name='idx_transaction_seller'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['created_at'], name='idx_transaction_created_at'),
        ),

        # ── LandParcel indexes ──────────────────────────────────────────
        migrations.AddIndex(
            model_name='landparcel',
            index=models.Index(
                fields=['verification_status'],
                name='idx_landparcel_verif_status',
            ),
        ),
        migrations.AddIndex(
            model_name='landparcel',
            index=models.Index(fields=['listed_by'], name='idx_landparcel_listed_by'),
        ),
        migrations.AddIndex(
            model_name='landparcel',
            index=models.Index(
                fields=['created_at'],
                name='idx_landparcel_created_at',
            ),
        ),
    ]
