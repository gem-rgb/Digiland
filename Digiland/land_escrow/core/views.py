from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404

from .models import User, LandParcel, Transaction, Document, AuditLog
from .serializers import (
    UserSerializer, RegisterSerializer, LoginSerializer,
    LandParcelSerializer, TransactionSerializer, DocumentSerializer
)
from .services import identity, land, document as document_service, risk, payment
from .validators import validate_file_upload
from django.db import models


def _get_client_ip(request):
    """Extract client IP address from request, respecting X-Forwarded-For."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """Register a new user. Admin role cannot be self-assigned."""
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        # SECURITY: Prevent Admin role self-assignment via API
        role = request.data.get('role', 'Buyer')
        if role == 'Admin':
            return Response(
                {"error": "Admin accounts cannot be created via registration."},
                status=status.HTTP_403_FORBIDDEN
            )
        user = serializer.save()
        
        # Generate JWT tokens for the newly registered user
        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "User registered successfully",
            "user": UserSerializer(user).data,
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """
    Authenticate user and return JWT tokens.
    
    SECURITY: Returns access + refresh tokens instead of user data.
    Access token has short lifetime (15 min); refresh token for renewal.
    """
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user and not existing_user.is_active:
            AuditLog.objects.create(
                user=existing_user,
                action='LOGIN_FAILURE',
                ip_address=_get_client_ip(request),
                metadata={'email': email[:3] + '***', 'reason': 'account_disabled'},
            )
            return Response(
                {"error": "Account is disabled. Contact support."},
                status=status.HTTP_403_FORBIDDEN
            )

        user = authenticate(
            email=email,
            password=password
        )
        if user:
            if not user.is_active:
                return Response(
                    {"error": "Account is disabled. Contact support."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Log successful login
            AuditLog.objects.create(
                user=user,
                action='LOGIN_SUCCESS',
                ip_address=_get_client_ip(request),
                metadata={'method': 'jwt'},
            )
            
            return Response({
                "message": "Login successful",
                "user": UserSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            }, status=status.HTTP_200_OK)
        
        # Log failed login attempt
        AuditLog.objects.create(
            user=None,
            action='LOGIN_FAILURE',
            ip_address=_get_client_ip(request),
            metadata={'email': serializer.validated_data['email'][:3] + '***'},
        )
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_identity(request, id):
    """Verify user identity. Users can only verify their own identity unless they are admin."""
    user = get_object_or_404(User, id=id)
    
    # SECURITY: Users can only verify their own identity (or admins can verify anyone)
    if request.user.id != user.id and request.user.role != 'Admin':
        return Response(
            {"error": "You can only verify your own identity."},
            status=status.HTTP_403_FORBIDDEN
        )
    
    success = identity.verify_user_identity(user)
    if success:
        return Response({
            "status": "success",
            "is_identity_verified": True,
            "gavakonect_verification_id": user.gavakonect_verification_id
        }, status=status.HTTP_200_OK)
    return Response(
        {"status": "failed", "message": "Identity verification failed"},
        status=status.HTTP_400_BAD_REQUEST
    )


class LandParcelViewSet(viewsets.ModelViewSet):
    queryset = LandParcel.objects.all()
    serializer_class = LandParcelSerializer
    lookup_field = 'parcel_number'
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        SECURITY: Filter parcels based on user role.
        - Buyers: see all verified parcels (read-only)
        - Sellers: see their own parcels + all verified parcels
        - Agents: see assigned parcels + all verified parcels
        - Admins: see all parcels
        """
        user = self.request.user
        if user.role == 'Admin':
            return LandParcel.objects.all()
        # For list/retrieve, show verified parcels + user's own
        return LandParcel.objects.filter(
            models.Q(verification_status='Verified') |
            models.Q(listed_by=user) |
            models.Q(assigned_agent=user)
        ).distinct()

    def perform_create(self, serializer):
        """Set the listed_by field to the current user."""
        serializer.save(listed_by=self.request.user)

    def perform_update(self, serializer):
        """SECURITY: Only the owner or admin can update a parcel."""
        parcel = self.get_object()
        if (parcel.listed_by != self.request.user and
                self.request.user.role != 'Admin'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only edit your own parcels.")
        serializer.save()

    def perform_destroy(self, instance):
        """SECURITY: Only the owner or admin can delete a parcel."""
        if (instance.listed_by != self.request.user and
                self.request.user.role != 'Admin'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You can only delete your own parcels.")
        instance.delete()

    def retrieve(self, request, parcel_number=None):
        parcel = self.get_object()
        mock_data = land.fetch_parcel_details(str(parcel.parcel_number))
        data = self.get_serializer(parcel).data
        data.update({'ardhisasa_verification': mock_data})
        return Response(data)

    @action(detail=True, methods=['post'], url_path='verify-ownership')
    def verify_ownership(self, request, parcel_number=None):
        claimed_owner_id_number = request.data.get('claimed_owner_id_number')
        result = land.verify_parcel_ownership(parcel_number, claimed_owner_id_number)
        return Response(result)

    @action(detail=True, methods=['get'], url_path='disputes')
    def get_disputes(self, request, parcel_number=None):
        disputes = land.check_for_disputes(parcel_number)
        return Response({"disputes": disputes})


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        SECURITY: Users can only see their own transactions.
        - Buyers: see transactions where they are the buyer
        - Sellers: see transactions where they are the seller
        - Agents: see transactions where they are the agent
        - Admins: see all transactions
        """
        user = self.request.user
        if user.role == 'Admin':
            return Transaction.objects.all()
        return Transaction.objects.filter(
            models.Q(buyer=user) |
            models.Q(seller=user) |
            models.Q(agent=user)
        ).distinct()

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        """SECURITY: Only admins can update transaction status directly."""
        if request.user.role != 'Admin':
            return Response(
                {"error": "Only administrators can update transaction status."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        transaction = self.get_object()
        new_status = request.data.get('status')
        
        # Validate status transition
        valid_transitions = {
            'Initiated': ['Deposit_Paid', 'Disputed'],
            'Deposit_Paid': ['Under_Verification', 'Verification_Hiatus', 'Disputed', 'Reversed'],
            'Under_Verification': ['Verification_Hiatus', 'Completed', 'Disputed'],
            'Verification_Hiatus': ['Under_Verification', 'Completed', 'Disputed', 'Reversed'],
            'Disputed': ['Refunded', 'Reversed'],
        }
        
        allowed = valid_transitions.get(transaction.status, [])
        if new_status not in allowed:
            return Response(
                {"error": f"Cannot transition from {transaction.status} to {new_status}. "
                 f"Allowed: {allowed}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transaction.status = new_status
        transaction.save()
        
        AuditLog.objects.create(
            user=request.user,
            action=f'TRANSACTION_STATUS_CHANGE: {transaction.id} -> {new_status}',
            ip_address=_get_client_ip(request),
            metadata={'transaction_id': str(transaction.id), 'old_status': transaction.status, 'new_status': new_status},
        )
        
        return Response({"status": "success", "transaction_status": transaction.status})

    @action(detail=True, methods=['get'], url_path='risk-report')
    def risk_report(self, request, pk=None):
        """SECURITY: Only participants or admins can view risk reports."""
        transaction = self.get_object()
        user = request.user
        if (user.role != 'Admin' and
                user != transaction.buyer and
                user != transaction.seller and
                user != transaction.agent):
            return Response(
                {"error": "You do not have permission to view this report."},
                status=status.HTTP_403_FORBIDDEN
            )
        report = risk.generate_transaction_risk_report(transaction)
        return Response(report)


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        SECURITY: Users can only see documents they uploaded or for their parcels.
        Admins can see all documents.
        """
        user = self.request.user
        if user.role == 'Admin':
            return Document.objects.all()
        return Document.objects.filter(
            models.Q(uploaded_by=user) |
            models.Q(land_parcel__listed_by=user) |
            models.Q(land_parcel__assigned_agent=user)
        ).distinct()

    def perform_create(self, serializer):
        """Set uploaded_by to current user and validate file."""
        # SECURITY: Validate file upload
        uploaded_file = self.request.FILES.get('file_url')
        if uploaded_file:
            validate_file_upload(
                uploaded_file,
                allowed_extensions=['.pdf', '.jpg', '.jpeg', '.png', '.webp'],
                allowed_mimes=[
                    'application/pdf',
                    'image/jpeg', 'image/png', 'image/webp',
                ],
                max_size_mb=10,
            )
        serializer.save(uploaded_by=self.request.user)

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
@permission_classes([IsAuthenticated])
def payment_deposit(request):
    transaction_id = request.data.get('transaction_id')
    amount = request.data.get('amount')
    gateway = request.data.get('gateway', 'mpesa').lower()
    
    transaction = get_object_or_404(Transaction, id=transaction_id)
    
    # SECURITY: Only transaction participants (buyer, seller, agent) or admins can deposit
    if (request.user != transaction.buyer and
            request.user != transaction.seller and
            (transaction.agent is None or request.user != transaction.agent) and
            request.user.role != 'Admin'):
        return Response(
            {"error": "You are not authorized to make payments for this transaction."},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if gateway == 'paystack':
        email = request.data.get('email', 'buyer@example.com')
        response = payment.paystack_initialize(email, amount, str(transaction.id))
    else:
        phone_number = request.data.get('phone_number', '254700000000')
        response = payment.mpesa_stk_push(phone_number, amount, str(transaction.id))
        
    payment.hold_payment(transaction)
    return Response(response, status=status.HTTP_200_OK)

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])  # Callbacks come from external services
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
@permission_classes([IsAuthenticated, IsAdminUser])
def payment_release(request, transaction_id):
    """SECURITY: Only admins can release payments to sellers."""
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
    
    AuditLog.objects.create(
        user=request.user,
        action=f'PAYMENT_RELEASED: Transaction {transaction.id}',
        ip_address=_get_client_ip(request),
        metadata={'transaction_id': str(transaction.id), 'amount': str(amount), 'gateway': gateway},
    )
    
    return Response(response, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def payment_refund(request, transaction_id):
    """SECURITY: Only admins can initiate refunds."""
    transaction = get_object_or_404(Transaction, id=transaction_id)
    payment.refund_payment_to_buyer(transaction)
    
    AuditLog.objects.create(
        user=request.user,
        action=f'REFUND_INITIATED: Transaction {transaction.id}',
        ip_address=_get_client_ip(request),
        metadata={'transaction_id': str(transaction.id), 'amount': str(transaction.agreed_price)},
    )
    
    return Response({"status": "success", "message": "Refund initialized via primary gateway."}, status=status.HTTP_200_OK)
