from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404

from .models import User, LandParcel, Transaction, Document, AuditLog
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,
    LandParcelSerializer, TransactionSerializer, DocumentSerializer
)
from .services import identity, land, document as document_service, risk, payment

@api_view(['POST'])
def register_user(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            "message": "User registered successfully", 
            "user": UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def login_user(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = authenticate(email=serializer.validated_data['email'], password=serializer.validated_data['password'])
        if user:
            # For a real implementation, return a JWT or DRF token here
            return Response({"message": "Login successful", "user": UserSerializer(user).data}, status=status.HTTP_200_OK)
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def verify_identity(request, id):
    user = get_object_or_404(User, id=id)
    # mock logic calls the identity service
    success = identity.verify_user_identity(user)
    if success:
        return Response({
            "status": "success",
            "is_identity_verified": True,
            "gavakonect_verification_id": user.gavakonect_verification_id
        }, status=status.HTTP_200_OK)
    return Response({"status": "failed", "message": "Identity verification failed"}, status=status.HTTP_400_BAD_REQUEST)


class LandParcelViewSet(viewsets.ModelViewSet):
    queryset = LandParcel.objects.all()
    serializer_class = LandParcelSerializer
    lookup_field = 'parcel_number'

    def retrieve(self, request, parcel_number=None):
        parcel = self.get_object()
        # Mocking the ArdhiSasa call alongside DB data
        mock_data = land.fetch_parcel_details(str(parcel.parcel_number))
        data = self.get_serializer(parcel).data
        data.update({'ardhisasa_verification': mock_data})
        return Response(data)

    @action(detail=True, methods=['post'], url_path='verify-ownership')
    def verify_ownership(request, parcel_number=None):
        claimed_owner_id_number = request.data.get('claimed_owner_id_number')
        result = land.verify_parcel_ownership(parcel_number, claimed_owner_id_number)
        return Response(result)

    @action(detail=True, methods=['get'], url_path='disputes')
    def get_disputes(request, parcel_number=None):
        disputes = land.check_for_disputes(parcel_number)
        return Response({"disputes": disputes})


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        transaction = self.get_object()
        new_status = request.data.get('status')
        if new_status in dict(Transaction.STATUS_CHOICES).keys():
            transaction.status = new_status
            transaction.save()
            return Response({"status": "success", "transaction_status": transaction.status})
        return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='risk-report')
    def risk_report(self, request, pk=None):
        transaction = self.get_object()
        report = risk.generate_transaction_risk_report(transaction)
        return Response(report)


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    @action(detail=True, methods=['post'], url_path='validate')
    def validate_document(self, request, pk=None):
        document_obj = self.get_object()
        if document_obj.document_type == 'Title_Deed':
            validation = document_service.validate_title_deed(
                document_obj.file_url,
                document_obj.land_parcel.parcel_number if document_obj.land_parcel else None,
            )
        else:
            validation = document_service.validate_id_document(
                document_obj.file_url,
                document_obj.uploaded_by.id_number,
            )

        status_map = {
            'APPROVED': 'Match',
            'FLAGGED_FOR_REVIEW': 'Forgery_Suspected',
            'REJECTED': 'Mismatch',
        }
        document_obj.verification_status = status_map.get(validation.get('status'), 'Mismatch')
        notes = validation.get('reason') or ''
        extra_notes = validation.get('reasons') or []
        if extra_notes:
            notes = '; '.join([note for note in [notes, *extra_notes] if note])
        if validation.get('tamper_flags'):
            tamper_notes = '; '.join(validation.get('tamper_flags'))
            notes = '; '.join([note for note in [notes, tamper_notes] if note])
        document_obj.fraud_flag_notes = notes or document_obj.fraud_flag_notes
        document_obj.save(update_fields=['verification_status', 'fraud_flag_notes'])

        AuditLog.objects.create(
            user=request.user,
            action=f'Document validation completed for {document_obj.id}',
            metadata={
                'document_id': str(document_obj.id),
                'document_type': document_obj.document_type,
                'verification_status': document_obj.verification_status,
                'status': validation.get('status'),
                'reason': validation.get('reason'),
                'ocr_confidence': validation.get('ocr_confidence'),
                'template_score': validation.get('template_score'),
            },
        )

        return Response({
            "verification_status": document_obj.verification_status,
            "fraud_flag_notes": document_obj.fraud_flag_notes,
            "details": validation,
        })

# Payments Endpoints
@api_view(['POST'])
def payment_deposit(request):
    transaction_id = request.data.get('transaction_id')
    amount = request.data.get('amount')
    gateway = request.data.get('gateway', 'mpesa').lower()
    
    transaction = get_object_or_404(Transaction, id=transaction_id)
    
    if gateway == 'paystack':
        email = request.data.get('email', 'buyer@example.com')
        response = payment.paystack_initialize(email, amount, str(transaction.id))
    else:
        phone_number = request.data.get('phone_number', '254700000000')
        response = payment.mpesa_stk_push(phone_number, amount, str(transaction.id))
        
    payment.hold_payment(transaction)
    return Response(response, status=status.HTTP_200_OK)

@api_view(['GET', 'POST'])
def payment_callback(request):
    from django.contrib import messages as django_messages
    from django.shortcuts import redirect

    payload = getattr(request, 'data', {}) or {}
    reference = (
        payload.get('data', {}).get('reference')
        or getattr(request, 'query_params', request.GET).get('reference')
        or payload.get('reference')
    )
    mpesa_payload = payload.get('Body', {}).get('stkCallback')

    if reference:
        verification = payment.paystack_verify(reference)
        transaction = Transaction.objects.filter(id=reference).first()
        paystack_success = bool(
            verification.get('status') == 'success'
            or verification.get('status') is True
            or verification.get('data', {}).get('status') == 'success'
        )

        if transaction and paystack_success:
            transaction.status = 'Deposit_Paid'
            transaction.escrow_reference = f"PAYSTACK-{reference}"
            transaction.save(update_fields=['status', 'escrow_reference'])
            AuditLog.objects.create(
                user=transaction.buyer,
                action=f'Paystack payment confirmed for transaction {transaction.id}',
                metadata={
                    'transaction_id': str(transaction.id),
                    'reference': reference,
                    'amount': str(transaction.agreed_price),
                },
            )

            if request.method == 'GET':
                django_messages.success(request, 'Paystack payment confirmed successfully.')
                return redirect('frontend:transactions')

            return Response({"message": "Paystack payment confirmed"}, status=status.HTTP_200_OK)

        if transaction:
            transaction.escrow_reference = f"FAILED-{reference}"
            transaction.save(update_fields=['escrow_reference'])

        if request.method == 'GET':
            if transaction:
                django_messages.error(request, 'Paystack payment could not be verified.')
                return redirect('frontend:transaction_failed', transaction_id=transaction.id)
            django_messages.error(request, 'Paystack payment could not be verified.')
            return redirect('frontend:transactions')

        return Response({"status": "failed", "message": "Paystack verification failed"}, status=status.HTTP_400_BAD_REQUEST)

    if mpesa_payload:
        return Response({"message": "Callback processed"}, status=status.HTTP_200_OK)

    if request.method == 'GET':
        return redirect('frontend:transactions')

    return Response({"message": "Callback processed"}, status=status.HTTP_200_OK)

@api_view(['POST'])
def payment_release(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    gateway = request.data.get('gateway', 'mpesa').lower()
    amount = transaction.agreed_price
    
    if gateway == 'paystack':
        mock_recipient_code = request.data.get('recipient_code', 'RCP_mockrecipient')
        response = payment.paystack_transfer(mock_recipient_code, amount)
    else:
        phone_number = transaction.seller.phone_number if transaction.seller else '254700000000'
        response = payment.mpesa_b2c_transfer(phone_number, amount, str(transaction.id))
        
    payment.release_payment_to_seller(transaction)
    return Response(response, status=status.HTTP_200_OK)

@api_view(['POST'])
def payment_refund(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    payment.refund_payment_to_buyer(transaction)
    return Response({"status": "success", "message": "Refund initialized via primary gateway."}, status=status.HTTP_200_OK)
