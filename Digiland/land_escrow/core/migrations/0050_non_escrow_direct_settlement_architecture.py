from django.db import migrations, models
import django.db.models.deletion


def backfill_direct_settlement_fields(apps, schema_editor):
    PaymentRecord = apps.get_model('core', 'PaymentRecord')
    for payment in PaymentRecord.objects.all():
        # Set payment_purpose
        if not payment.payment_purpose:
            payment.payment_purpose = payment.purpose or 'LAND_PURCHASE'

        # Set payment_type and beneficiary_type
        if payment.payment_purpose == 'DIGILAND_SERVICE_FEE':
            payment.payment_type = 'PLATFORM_COLLECTION'
            payment.beneficiary_type = 'DIGILAND'
            payment.beneficiary_name = 'DigiLand Ltd'
        elif payment.payment_purpose in ['SURVEY_FEE', 'LEGAL_FEE', 'INSPECTION_FEE']:
            payment.payment_type = 'PROFESSIONAL_PAYMENT'
            if payment.payment_purpose == 'SURVEY_FEE':
                payment.beneficiary_type = 'SURVEYOR'
                payment.service_type = 'LAND_SURVEY'
            elif payment.payment_purpose == 'LEGAL_FEE':
                payment.beneficiary_type = 'ADVOCATE'
                payment.service_type = 'LEGAL_CONVEYANCING'
            else:
                payment.beneficiary_type = 'FIELD_AGENT'
                payment.service_type = 'SITE_INSPECTION'
            payment.beneficiary_user = payment.recipient
            payment.beneficiary_name = payment.recipient.get_full_name() if payment.recipient else 'Professional Service Provider'
        else:
            payment.payment_type = 'DIRECT_SETTLEMENT'
            payment.beneficiary_type = 'SELLER'
            if payment.recipient:
                payment.beneficiary_user = payment.recipient
                payment.beneficiary_name = payment.recipient.get_full_name() or payment.recipient.email
            elif payment.transaction and payment.transaction.seller:
                payment.beneficiary_user = payment.transaction.seller
                payment.beneficiary_name = payment.transaction.seller.get_full_name() or payment.transaction.seller.email
            else:
                payment.beneficiary_name = 'Seller'

        payment.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_mpesa_payment_architecture_and_refunds'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentrecord',
            name='payment_type',
            field=models.CharField(
                choices=[
                    ('DIRECT_SETTLEMENT', 'Direct Settlement (Buyer to Seller)'),
                    ('PLATFORM_COLLECTION', 'DigiLand Platform Collection'),
                    ('PROFESSIONAL_PAYMENT', 'Professional Direct Payment')
                ],
                default='DIRECT_SETTLEMENT',
                max_length=40,
                db_index=True
            ),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='payment_purpose',
            field=models.CharField(
                choices=[
                    ('LAND_PURCHASE', 'Land Purchase Consideration'),
                    ('DIGILAND_SERVICE_FEE', 'DigiLand Platform / Coordination Fee'),
                    ('SURVEY_FEE', 'Surveyor Verification Fee'),
                    ('LEGAL_FEE', 'Legal Conveyance Fee'),
                    ('INSPECTION_FEE', 'Physical Site Inspection Fee'),
                    ('ADDITIONAL_DUE_DILIGENCE_FEE', 'Additional Due Diligence Fee'),
                    ('OTHER', 'Other Service Fee')
                ],
                default='LAND_PURCHASE',
                max_length=50,
                db_index=True
            ),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='beneficiary_type',
            field=models.CharField(
                choices=[
                    ('SELLER', 'Land Seller'),
                    ('DIGILAND', 'DigiLand Platform'),
                    ('SURVEYOR', 'Licensed Surveyor'),
                    ('ADVOCATE', 'Conveyancing Advocate'),
                    ('FIELD_AGENT', 'Field Inspection Agent'),
                    ('OTHER', 'Other Service Provider')
                ],
                default='SELLER',
                max_length=30,
                db_index=True
            ),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='beneficiary_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='payments_as_beneficiary',
                to='core.user'
            ),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='beneficiary_name',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='service_type',
            field=models.CharField(blank=True, help_text='Specific service type e.g. LAND_SURVEY, TITLE_SEARCH, SITE_INSPECTION', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='paymentrecord',
            name='is_legacy_record',
            field=models.BooleanField(default=False, help_text='True if record is a preserved legacy entry'),
        ),
        migrations.AddIndex(
            model_name='paymentrecord',
            index=models.Index(fields=['payment_type', 'status'], name='idx_pmt_type_status'),
        ),
        migrations.AddIndex(
            model_name='paymentrecord',
            index=models.Index(fields=['beneficiary_type', 'status'], name='idx_pmt_ben_status'),
        ),
        migrations.RunPython(backfill_direct_settlement_fields, migrations.RunPython.noop),
    ]
