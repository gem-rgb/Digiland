from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from core.models import Transaction, User
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check verification deadlines and send notifications for overdue transactions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto-reverse',
            action='store_true',
            help='Automatically reverse payments for transactions with passed deadlines',
        )
        parser.add_argument(
            '--notify-only',
            action='store_true',
            help='Only send notifications without taking action',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Find transactions with passed deadlines
        overdue_transactions = Transaction.objects.filter(
            status='Verification_Hiatus',
            buyer_validation_deadline__lt=now
        )
        
        if not overdue_transactions.exists():
            self.stdout.write(self.style.SUCCESS('No overdue verification deadlines found.'))
            return
        
        self.stdout.write(
            self.style.WARNING(f'Found {overdue_transactions.count()} overdue transactions')
        )
        
        for transaction in overdue_transactions:
            days_overdue = (now - transaction.buyer_validation_deadline).days
            
            self.stdout.write(
                f"Transaction {transaction.id}: {days_overdue} days overdue"
            )
            
            # Send notifications
            self.send_notifications(transaction, days_overdue)
            
            # Auto-reverse if requested
            if options.get('auto_reverse'):
                try:
                    reversal_ref = transaction.reverse_payment(
                        User.objects.filter(role='Admin').first(),
                        f"Automatic reversal - verification deadline passed by {days_overdue} days"
                    )
                    self.stdout.write(
                        self.style.SUCCESS(f"Auto-reversed transaction {transaction.id} - Ref: {reversal_ref}")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Failed to reverse transaction {transaction.id}: {str(e)}")
                    )
        
        self.stdout.write(
            self.style.SUCCESS('Verification deadline check completed.')
        )

    def send_notifications(self, transaction, days_overdue):
        """Send email notifications to buyer, seller, and admin"""
        
        # Send to buyer
        try:
            send_mail(
                subject=f'⚠️ Verification Deadline Passed - Transaction {transaction.id}',
                message=f'''
Dear {transaction.buyer.email},

The 7-day verification period for your land transaction has passed {days_overdue} days ago.

Transaction Details:
- Transaction ID: {transaction.id}
- Land Parcel: {transaction.land_parcel.parcel_number}
- Amount: KES {transaction.agreed_price}
- Deadline: {transaction.buyer_validation_deadline.strftime("%B %d, %Y")}

Please contact support immediately to resolve this issue.

Best regards,
Digiland Team
                '''.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[transaction.buyer.email],
                fail_silently=False,
            )
            self.stdout.write(f"Sent notification to buyer: {transaction.buyer.email}")
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to send email to buyer: {str(e)}")
            )
        
        # Send to seller
        try:
            send_mail(
                subject=f'⚠️ Verification Deadline Passed - Transaction {transaction.id}',
                message=f'''
Dear {transaction.seller.email},

The 7-day verification period for your land transaction has passed {days_overdue} days ago.

Transaction Details:
- Transaction ID: {transaction.id}
- Land Parcel: {transaction.land_parcel.parcel_number}
- Amount: KES {transaction.agreed_price}
- Buyer: {transaction.buyer.email}
- Deadline: {transaction.buyer_validation_deadline.strftime("%B %d, %Y")}

Please contact support immediately to resolve this issue.

Best regards,
Digiland Team
                '''.strip(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[transaction.seller.email],
                fail_silently=False,
            )
            self.stdout.write(f"Sent notification to seller: {transaction.seller.email}")
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to send email to seller: {str(e)}")
            )
        
        # Send to admin
        try:
            admin_users = User.objects.filter(role='Admin')
            if admin_users.exists():
                send_mail(
                    subject=f'🚨 Overdue Verification Deadline - {overdue_transactions.count()} Transactions',
                    message=f'''
Admin Alert,

{overdue_transactions.count()} transactions have passed their 7-day verification deadline.

Most Recent Overdue Transaction:
- Transaction ID: {transaction.id}
- Land Parcel: {transaction.land_parcel.parcel_number}
- Amount: KES {transaction.agreed_price}
- Days Overdue: {days_overdue}
- Buyer: {transaction.buyer.email}
- Seller: {transaction.seller.email}

Please review these transactions in the admin dashboard and take appropriate action.

Admin Dashboard: {settings.SITE_URL}/admin/verification-dashboard/

Best regards,
Digiland System
                    '''.strip(),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin.email for admin in admin_users],
                    fail_silently=False,
                )
                self.stdout.write(f"Sent notification to {admin_users.count()} admin users")
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to send email to admins: {str(e)}")
            )
