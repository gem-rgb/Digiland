import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from .models import User, AgentKYCApplication
from .services.identity import GavaConnectAPI, verify_user_kra_pin
from .services.payment import DarajaAPI

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(View):
    """
    Handle M-PESA Daraja API callbacks for STK Push and B2C transactions
    """
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            logger.info(f"M-PESA Callback received: {data}")
            
            # Handle STK Push callback
            if 'Body' in data and 'stkCallback' in data['Body']:
                return self.handle_stk_callback(data['Body']['stkCallback'])
            
            # Handle B2C callback
            elif 'Result' in data:
                return self.handle_b2c_callback(data['Result'])
            
            else:
                logger.warning("Unknown M-PESA callback format")
                return JsonResponse({"status": "error", "message": "Unknown callback format"})
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON in M-PESA callback")
            return JsonResponse({"status": "error", "message": "Invalid JSON"})
        except Exception as e:
            logger.error(f"Error processing M-PESA callback: {str(e)}")
            return JsonResponse({"status": "error", "message": "Internal error"})
    
    def handle_stk_callback(self, callback_data):
        """
        Handle STK Push transaction callback
        """
        try:
            result_code = callback_data.get('ResultCode')
            checkout_request_id = callback_data.get('CheckoutRequestID')
            
            if result_code == 0:  # Success
                # Extract transaction details from metadata
                metadata = callback_data.get('CallbackMetadata', {}).get('Item', [])
                amount = phone = mpesa_receipt = None
                
                for item in metadata:
                    name = item.get('Name')
                    value = item.get('Value')
                    if name == 'Amount':
                        amount = value
                    elif name == 'PhoneNumber':
                        phone = value
                    elif name == 'MpesaReceiptNumber':
                        mpesa_receipt = value
                
                logger.info(f"STK Push successful: {mpesa_receipt}, Amount: {amount}, Phone: {phone}")
                
                # Here you would typically update your transaction model
                # For example: Transaction.objects.filter(checkout_request_id=checkout_request_id).update(status='paid')
                
                return JsonResponse({"status": "success", "message": "Payment processed successfully"})
            else:
                result_desc = callback_data.get('ResultDesc', 'Transaction failed')
                logger.warning(f"STK Push failed: {result_desc}")
                
                # Update transaction status to failed
                # Transaction.objects.filter(checkout_request_id=checkout_request_id).update(status='failed')
                
                return JsonResponse({"status": "failed", "message": result_desc})
                
        except Exception as e:
            logger.error(f"Error handling STK callback: {str(e)}")
            return JsonResponse({"status": "error", "message": "Callback processing error"})
    
    def handle_b2c_callback(self, result_data):
        """
        Handle B2C transaction callback
        """
        try:
            result_code = result_data.get('ResultCode')
            conversation_id = result_data.get('ConversationID')
            
            if result_code == 0:  # Success
                result_parameters = result_data.get('ResultParameters', {}).get('ResultParameter', [])
                
                # Extract transaction details
                transaction_amount = None
                transaction_receipt = None
                receiver_phone = None
                
                for param in result_parameters:
                    key = param.get('Key')
                    value = param.get('Value')
                    if key == 'TransactionAmount':
                        transaction_amount = value
                    elif key == 'TransReceipt':
                        transaction_receipt = value
                    elif key == 'ReceiverPartyPublicName':
                        receiver_phone = value
                
                logger.info(f"B2C successful: {transaction_receipt}, Amount: {transaction_amount}, Receiver: {receiver_phone}")
                
                # Update escrow transaction status to completed
                # Transaction.objects.filter(conversation_id=conversation_id).update(status='completed')
                
                return JsonResponse({"status": "success", "message": "B2C payment completed successfully"})
            else:
                result_desc = result_data.get('ResultDesc', 'B2C transaction failed')
                logger.warning(f"B2C failed: {result_desc}")
                
                # Update transaction status to failed
                # Transaction.objects.filter(conversation_id=conversation_id).update(status='failed')
                
                return JsonResponse({"status": "failed", "message": result_desc})
                
        except Exception as e:
            logger.error(f"Error handling B2C callback: {str(e)}")
            return JsonResponse({"status": "error", "message": "B2C callback processing error"})

@csrf_exempt
@require_http_methods(["POST"])
def verify_kra_pin_view(request):
    """
    API endpoint to verify KRA PIN using GavaConnect
    """
    try:
        data = json.loads(request.body)
        kra_pin = data.get('kra_pin')
        id_number = data.get('id_number')
        user_id = data.get('user_id')
        
        if not kra_pin:
            return JsonResponse({"status": "error", "message": "KRA PIN is required"})
        
        # Verify KRA PIN
        result = GavaConnectAPI.verify_kra_pin(kra_pin, id_number)
        
        if result.get("status") == "success" and result.get("is_valid"):
            # If user_id is provided, update user's verification status
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    user.is_identity_verified = True
                    user.gavakonect_verification_id = result.get("verification_id")
                    user.save()
                    
                    # If user has KYC application, update it too
                    if hasattr(user, 'kyc_application'):
                        kyc_app = user.kyc_application
                        kyc_app.kra_pin = kra_pin
                        kyc_app.save()
                    
                    logger.info(f"KRA PIN verified and user updated: {user.email}")
                    
                except User.DoesNotExist:
                    logger.warning(f"User not found for ID: {user_id}")
            
            return JsonResponse({
                "status": "success",
                "message": "KRA PIN verified successfully",
                "verification_details": {
                    "business_name": result.get("business_name"),
                    "registration_date": result.get("registration_date"),
                    "verification_id": result.get("verification_id")
                }
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": result.get("message", "KRA PIN verification failed")
            })
            
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error in KRA PIN verification: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal verification error"})

@csrf_exempt
@require_http_methods(["POST"])
def verify_identity_view(request):
    """
    API endpoint to verify user identity using GavaConnect
    """
    try:
        data = json.loads(request.body)
        id_number = data.get('id_number')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        user_id = data.get('user_id')
        
        if not id_number:
            return JsonResponse({"status": "error", "message": "ID number is required"})
        
        # Verify identity
        result = GavaConnectAPI.verify_id_number(id_number, first_name, last_name)
        
        if result.get("status") == "success" and result.get("is_valid"):
            # If user_id is provided, update user's verification status
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    user.is_identity_verified = True
                    user.gavakonect_verification_id = result.get("verification_id")
                    user.save()
                    
                    logger.info(f"Identity verified and user updated: {user.email}")
                    
                except User.DoesNotExist:
                    logger.warning(f"User not found for ID: {user_id}")
            
            return JsonResponse({
                "status": "success",
                "message": "Identity verified successfully",
                "verification_details": {
                    "full_name": result.get("full_name"),
                    "date_of_birth": result.get("date_of_birth"),
                    "gender": result.get("gender"),
                    "county": result.get("county"),
                    "verification_id": result.get("verification_id")
                }
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": result.get("message", "Identity verification failed")
            })
            
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error in identity verification: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal verification error"})

@csrf_exempt
@require_http_methods(["POST"])
def verify_business_view(request):
    """
    API endpoint to verify business registration using GavaConnect
    """
    try:
        data = json.loads(request.body)
        business_name = data.get('business_name')
        registration_number = data.get('registration_number')
        
        if not business_name:
            return JsonResponse({"status": "error", "message": "Business name is required"})
        
        # Verify business registration
        result = GavaConnectAPI.verify_business_registration(business_name, registration_number)
        
        if result.get("status") == "success" and result.get("is_valid"):
            return JsonResponse({
                "status": "success",
                "message": "Business registration verified successfully",
                "verification_details": {
                    "registration_number": result.get("registration_number"),
                    "registration_date": result.get("registration_date"),
                    "business_type": result.get("business_type"),
                    "registered_address": result.get("registered_address"),
                    "directors": result.get("directors", []),
                    "verification_id": result.get("verification_id")
                }
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": result.get("message", "Business verification failed")
            })
            
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error in business verification: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal verification error"})

@csrf_exempt
@require_http_methods(["POST"])
def initiate_mpesa_payment_view(request):
    """
    API endpoint to initiate M-PESA STK Push payment
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        amount = data.get('amount')
        transaction_id = data.get('transaction_id')
        
        if not all([phone_number, amount, transaction_id]):
            return JsonResponse({
                "status": "error", 
                "message": "Phone number, amount, and transaction ID are required"
            })
        
        # Initiate STK Push
        result = DarajaAPI.stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=f"ESCROW-{transaction_id}",
            transaction_desc=f"Land escrow payment for transaction {transaction_id}"
        )
        
        if result.get("status") == "success":
            return JsonResponse({
                "status": "success",
                "message": "M-PESA payment initiated successfully",
                "payment_details": {
                    "checkout_request_id": result.get("checkout_request_id"),
                    "merchant_request_id": result.get("merchant_request_id"),
                    "customer_message": result.get("customer_message")
                }
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": result.get("message", "M-PESA payment initiation failed")
            })
            
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error initiating M-PESA payment: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal payment error"})

@csrf_exempt
@require_http_methods(["POST"])
def query_mpesa_status_view(request):
    """
    API endpoint to query M-PESA STK Push transaction status
    """
    try:
        data = json.loads(request.body)
        checkout_request_id = data.get('checkout_request_id')
        
        if not checkout_request_id:
            return JsonResponse({"status": "error", "message": "Checkout request ID is required"})
        
        # Query transaction status
        result = DarajaAPI.query_stk_status(checkout_request_id)
        
        return JsonResponse(result)
            
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error querying M-PESA status: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal status query error"})
