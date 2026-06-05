from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Transaction
from .services.payment import DarajaAPI
import logging

logger = logging.getLogger(__name__)

@staff_member_required
def reverse_payment_confirmation(request):
    """
    Admin view for confirming payment reversal
    """
    if request.method == 'GET':
        transaction_ids = request.session.get('reversal_transactions', [])
        if not transaction_ids:
            messages.error(request, 'No transactions selected for reversal.')
            return redirect('admin:core_transaction_changelist')
        
        transactions = Transaction.objects.filter(id__in=transaction_ids)
        
        # Validate that all transactions can be reversed
        reversible_transactions = []
        non_reversible = []
        
        for transaction in transactions:
            if transaction.status in ['Deposit_Paid', 'Under_Verification', 'Verification_Hiatus']:
                reversible_transactions.append(transaction)
            else:
                non_reversible.append(transaction)
        
        context = {
            'reversible_transactions': reversible_transactions,
            'non_reversible': non_reversible,
            'total_amount': sum(t.agreed_price for t in reversible_transactions),
        }
        
        return render(request, 'admin/reverse_payment_confirmation.html', context)
    
    elif request.method == 'POST':
        transaction_ids = request.POST.getlist('transaction_ids')
        reversal_reason = request.POST.get('reversal_reason', 'Payment reversal by admin')
        
        if not transaction_ids:
            messages.error(request, 'No transactions selected for reversal.')
            return redirect('admin:core_transaction_changelist')
        
        successful_reversals = []
        failed_reversals = []
        
        for transaction_id in transaction_ids:
            try:
                transaction = Transaction.objects.get(id=transaction_id)
                
                # Check if transaction can be reversed
                if transaction.status not in ['Deposit_Paid', 'Under_Verification', 'Verification_Hiatus']:
                    failed_reversals.append({
                        'transaction': transaction,
                        'reason': f'Cannot reverse transaction in status: {transaction.status}'
                    })
                    continue
                
                # Initiate reversal
                reversal_ref = transaction.reverse_payment(request.user, reversal_reason)
                successful_reversals.append({
                    'transaction': transaction,
                    'reversal_reference': reversal_ref
                })
                
                # Log the reversal
                logger.info(f"Payment reversal initiated for transaction {transaction.id} by admin {request.user.email}")
                
            except Exception as e:
                failed_reversals.append({
                    'transaction_id': transaction_id,
                    'reason': str(e)
                })
                logger.error(f"Failed to reverse transaction {transaction_id}: {str(e)}")
        
        # Clear session data
        if 'reversal_transactions' in request.session:
            del request.session['reversal_transactions']
        
        # Show results
        if successful_reversals:
            messages.success(
                request, 
                f'Successfully initiated reversal for {len(successful_reversals)} transaction(s).'
            )
        
        if failed_reversals:
            messages.error(
                request,
                f'Failed to reverse {len(failed_reversals)} transaction(s). Check logs for details.'
            )
        
        return redirect('admin:core_transaction_changelist')

@staff_member_required
@require_http_methods(["POST"])
def ajax_reverse_single_payment(request):
    """
    AJAX endpoint for reversing a single transaction
    """
    transaction_id = request.POST.get('transaction_id')
    reversal_reason = request.POST.get('reversal_reason', 'Payment reversal by admin')
    
    if not transaction_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Transaction ID is required'
        })
    
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        # Check if transaction can be reversed
        if transaction.status not in ['Deposit_Paid', 'Under_Verification', 'Verification_Hiatus']:
            return JsonResponse({
                'status': 'error',
                'message': f'Cannot reverse transaction in status: {transaction.status}'
            })
        
        # Initiate reversal
        reversal_ref = transaction.reverse_payment(request.user, reversal_reason)
        
        logger.info(f"Payment reversal initiated for transaction {transaction.id} by admin {request.user.email}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Payment reversal initiated successfully',
            'reversal_reference': reversal_ref,
            'transaction_id': str(transaction.id)
        })
        
    except Transaction.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Transaction not found'
        })
    except Exception as e:
        logger.error(f"Failed to reverse transaction {transaction_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@staff_member_required
def verification_dashboard(request):
    """
    Admin dashboard for managing verification hiatus periods
    """
    # Get transactions in various verification states
    awaiting_hiatus = Transaction.objects.filter(status='Deposit_Paid')
    in_hiatus = Transaction.objects.filter(status='Verification_Hiatus')
    deadline_passed = Transaction.objects.filter(
        status='Verification_Hiatus',
        buyer_validation_deadline__lt=timezone.now()
    )
    verified = Transaction.objects.filter(land_verified=True)
    
    # Calculate statistics
    context = {
        'awaiting_hiatus_count': awaiting_hiatus.count(),
        'in_hiatus_count': in_hiatus.count(),
        'deadline_passed_count': deadline_passed.count(),
        'verified_count': verified.count(),
        'awaiting_hiatus': awaiting_hiatus[:10],  # Show recent 10
        'in_hiatus': in_hiatus[:10],
        'deadline_passed': deadline_passed[:10],
    }
    
    return render(request, 'admin/verification_dashboard.html', context)

@staff_member_required
@require_http_methods(["POST"])
def ajax_complete_verification(request):
    """
    AJAX endpoint for completing land verification
    """
    transaction_id = request.POST.get('transaction_id')
    verification_notes = request.POST.get('verification_notes', 'Verification completed by admin')
    
    if not transaction_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Transaction ID is required'
        })
    
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        if not transaction.is_in_verification_hiatus:
            return JsonResponse({
                'status': 'error',
                'message': 'Transaction is not in verification hiatus'
            })
        
        # Complete verification
        transaction.complete_verification(request.user, verification_notes)
        
        logger.info(f"Land verification completed for transaction {transaction.id} by admin {request.user.email}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Land verification completed successfully',
            'transaction_id': str(transaction.id)
        })
        
    except Transaction.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Transaction not found'
        })
    except Exception as e:
        logger.error(f"Failed to complete verification for transaction {transaction_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })

@staff_member_required
@require_http_methods(["POST"])
def ajax_start_hiatus(request):
    """
    AJAX endpoint for starting verification hiatus
    """
    transaction_id = request.POST.get('transaction_id')
    
    if not transaction_id:
        return JsonResponse({
            'status': 'error',
            'message': 'Transaction ID is required'
        })
    
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        
        if transaction.status != 'Deposit_Paid':
            return JsonResponse({
                'status': 'error',
                'message': 'Transaction must be in Deposit_Paid status to start hiatus'
            })
        
        # Start verification hiatus
        transaction.start_verification_hiatus()
        
        logger.info(f"Verification hiatus started for transaction {transaction.id} by admin {request.user.email}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Verification hiatus started successfully',
            'transaction_id': str(transaction.id),
            'deadline': transaction.buyer_validation_deadline.isoformat() if transaction.buyer_validation_deadline else None
        })
        
    except Transaction.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Transaction not found'
        })
    except Exception as e:
        logger.error(f"Failed to start verification hiatus for transaction {transaction_id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })
