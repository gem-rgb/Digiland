from rest_framework import serializers
from .models import User, LandParcel, Transaction, Document, AuditLog

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'id_number', 'phone_number', 'role', 'is_identity_verified', 'gavakonect_verification_id']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'id_number', 'phone_number', 'role']

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            id_number=validated_data.get('id_number', ''),
            phone_number=validated_data.get('phone_number', ''),
            role=validated_data.get('role', 'Buyer')
        )
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

class LandParcelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandParcel
        fields = '__all__'

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ['status', 'escrow_reference']

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'
        read_only_fields = ['verification_status', 'fraud_flag_notes']
