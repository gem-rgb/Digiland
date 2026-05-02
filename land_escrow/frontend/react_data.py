from django import forms as django_forms
from django.contrib.messages import get_messages
from django.urls import reverse


def build_nav(user, active=None):
    active = active or ''
    role = getattr(user, 'role', None)
    is_authenticated = getattr(user, 'is_authenticated', False)

    if not is_authenticated:
        return [
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'icon': 'parcels', 'active': active == 'parcel-list'},
            {'label': 'Legal', 'href': reverse('frontend:escrow_acts'), 'icon': 'legal', 'active': active in {'legal', 'joint-laws'}},
        ]

    if role == 'Buyer':
        nav = [
            {'label': 'Dashboard', 'href': reverse('frontend:home'), 'icon': 'dashboard', 'active': active == 'dashboard'},
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'icon': 'parcels', 'active': active == 'parcel-list'},
            {'label': 'Transactions', 'href': reverse('frontend:transactions'), 'icon': 'transactions', 'active': active == 'transactions'},
            {'label': 'My Groups', 'href': reverse('frontend:joint_groups'), 'icon': 'joint', 'active': active.startswith('joint')},
            {'label': 'Legal', 'href': reverse('frontend:escrow_acts'), 'icon': 'legal', 'active': active in {'legal', 'joint-laws'}},
        ]
        if getattr(user, 'buyer_account_type', None) == 'Joint':
            nav.insert(3, {'label': 'Buyer Setup', 'href': reverse('frontend:buyer_account_choice'), 'icon': 'security', 'active': active == 'buyer-choice'})
        return nav

    if role == 'Seller':
        return [
            {'label': 'Dashboard', 'href': reverse('frontend:home'), 'icon': 'dashboard', 'active': active == 'dashboard'},
            {'label': 'My Parcels', 'href': reverse('frontend:parcel_list'), 'icon': 'parcels', 'active': active == 'parcel-list'},
            {'label': 'Transactions', 'href': reverse('frontend:transactions'), 'icon': 'transactions', 'active': active == 'transactions'},
            {'label': 'Legal', 'href': reverse('frontend:escrow_acts'), 'icon': 'legal', 'active': active in {'legal', 'joint-laws'}},
        ]

    return [
        {'label': 'Command Centre', 'href': reverse('frontend:agent_dashboard'), 'icon': 'dashboard', 'active': active in {'dashboard', 'admin-dashboard', 'agent-dashboard'}},
        {'label': 'Tasks', 'href': reverse('frontend:task_management'), 'icon': 'parcels', 'active': active == 'tasks'},
        {'label': 'Parcels', 'href': reverse('frontend:parcel_list'), 'icon': 'parcels', 'active': active == 'parcel-list'},
        {'label': 'Transactions', 'href': reverse('frontend:transactions'), 'icon': 'transactions', 'active': active == 'transactions'},
        {'label': 'Messages', 'href': reverse('frontend:messages'), 'icon': 'documents', 'active': active == 'messages'},
    ]


def serialize_user(user):
    if not getattr(user, 'is_authenticated', False):
        return None

    full_name = (f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}").strip() or getattr(user, 'email', '')
    return {
        'email': user.email,
        'role': getattr(user, 'role', ''),
        'buyer_account_type': getattr(user, 'buyer_account_type', None),
        'is_identity_verified': getattr(user, 'is_identity_verified', False),
        'full_name': full_name,
        'phone_number': getattr(user, 'phone_number', None),
    }


def serialize_review_user(user):
    data = serialize_user(user) or {}
    data.update({
        'id': str(user.id),
        'is_active': getattr(user, 'is_active', None),
        'id_number': getattr(user, 'id_number', None),
        'phone_number': getattr(user, 'phone_number', None),
        'kra_pin': getattr(user, 'kra_pin', None),
        'joined_at': user.date_joined.strftime('%b %d, %Y') if getattr(user, 'date_joined', None) else None,
        'role_label': getattr(user, 'role', ''),
    })
    return data


def serialize_parcel(parcel, user=None):
    is_owner = bool(user and getattr(user, 'id', None) == getattr(parcel.listed_by, 'id', None))
    is_admin = bool(user and getattr(user, 'role', None) == 'Admin')
    return {
        'parcel_number': str(parcel.parcel_number),
        'county': parcel.county,
        'constituency': parcel.constituency,
        'ward': parcel.ward,
        'land_size': str(parcel.land_size),
        'land_use_type': parcel.land_use_type,
        'verification_status': parcel.verification_status,
        'image_url': parcel.image.url if getattr(parcel, 'image', None) else None,
        'details_url': reverse('frontend:parcel_detail', args=[parcel.parcel_number]),
        'manage_label': 'Manage Listing' if (is_owner or is_admin) else 'View Details and Buy',
        'manage_url': reverse('frontend:parcel_detail', args=[parcel.parcel_number]),
        'status_badge': parcel.get_verification_status_display() if hasattr(parcel, 'get_verification_status_display') else parcel.verification_status,
    }


def serialize_document(document):
    return {
        'id': str(document.id),
        'document_type': document.document_type,
        'document_label': document.get_document_type_display() if hasattr(document, 'get_document_type_display') else document.document_type,
        'verification_status': document.verification_status,
        'uploaded_at': document.uploaded_at.strftime('%b %d, %Y') if getattr(document, 'uploaded_at', None) else '',
        'file_url': document.file_url.url if getattr(document, 'file_url', None) else None,
    }


def serialize_transaction(tx, user=None):
    role_label = 'Buyer' if user and getattr(user, 'id', None) == getattr(tx, 'buyer_id', None) else 'Seller'
    if user and getattr(user, 'role', None) == 'Admin':
        role_label = 'Admin'
    status_tone = 'muted'
    if tx.status in {'Completed'}:
        status_tone = 'success'
    elif tx.status in {'Deposit_Paid', 'Under_Verification'}:
        status_tone = 'accent'
    elif tx.status in {'Reversed', 'Refunded', 'Disputed'}:
        status_tone = 'danger'
    elif tx.status in {'Initiated'}:
        status_tone = 'warning'

    action_label = 'View Contract'
    if tx.status == 'Completed':
        action_label = 'Archived Contract'
    elif tx.status in {'Reversed', 'Refunded', 'Disputed'}:
        action_label = 'View Details'
    elif user and getattr(user, 'id', None) == getattr(tx, 'buyer_id', None) and not tx.buyer_signature:
        action_label = 'Sign Agreement'
    elif user and getattr(user, 'id', None) == getattr(tx, 'seller_id', None) and not tx.seller_signature:
        action_label = 'Sign Agreement'

    return {
        'id': str(tx.id),
        'parcel_number': tx.land_parcel.parcel_number,
        'role_label': role_label,
        'amount': str(tx.agreed_price),
        'status': tx.get_status_display() if hasattr(tx, 'get_status_display') else tx.status,
        'status_tone': status_tone,
        'created_at': tx.created_at.strftime('%b %d, %Y'),
        'action_label': action_label,
        'action_url': reverse('frontend:sign_contract', args=[tx.id]),
        'is_joint_purchase': bool(getattr(tx, 'is_joint_purchase', False)),
        'joint_label': 'Joint' if getattr(tx, 'is_joint_purchase', False) else '',
    }


def serialize_status_page(*, title, description, tone='default', icon=None, primary_action=None, secondary_action=None, extra_actions=None):
    return {
        'icon': icon,
        'tone': tone,
        'title': title,
        'description': description,
        'primary_action': primary_action,
        'secondary_action': secondary_action,
        'extra_actions': extra_actions or [],
    }


def serialize_contract(transaction, user, *, laws, joint_breakdown=None, sign_url, payment_url, transactions_url, csrf_token):
    joint_breakdown_data = []
    for row in joint_breakdown or []:
        member = row.get('member')
        joint_breakdown_data.append({
            'member': serialize_joint_member(member),
            'amount': str(row.get('amount', '0')),
        })

    return {
        'transaction_id': str(transaction.id),
        'parcel_number': transaction.land_parcel.parcel_number,
        'buyer_email': transaction.buyer.email,
        'seller_email': transaction.seller.email,
        'agreed_price': str(transaction.agreed_price),
        'contract_agreed': bool(transaction.contract_agreed),
        'buyer_signature_present': bool(transaction.buyer_signature),
        'seller_signature_present': bool(transaction.seller_signature),
        'is_joint_purchase': bool(transaction.is_joint_purchase),
        'joint_group_name': transaction.joint_group.name if transaction.is_joint_purchase and transaction.joint_group else None,
        'joint_group_ownership': transaction.joint_group.get_ownership_type_display() if transaction.is_joint_purchase and transaction.joint_group else None,
        'joint_breakdown': joint_breakdown_data,
        'laws': [serialize_law(law) for law in laws],
        'current_user_role': getattr(user, 'role', ''),
        'current_user_is_buyer': getattr(user, 'id', None) == getattr(transaction, 'buyer_id', None),
        'current_user_is_seller': getattr(user, 'id', None) == getattr(transaction, 'seller_id', None),
        'current_user_is_admin': getattr(user, 'role', None) == 'Admin',
        'current_user_is_joint_leader': bool(
            transaction.is_joint_purchase
            and transaction.joint_group
            and getattr(transaction.joint_group, 'leader_id', None) == getattr(user, 'id', None)
        ),
        'sign_url': sign_url,
        'payment_url': payment_url,
        'transactions_url': transactions_url,
        'csrf_token': csrf_token,
        'signature_data_name': 'signature_data',
        'admin_dual_sign': getattr(user, 'role', None) == 'Admin',
    }


def serialize_checkout(
    transaction,
    user,
    *,
    joint_breakdown=None,
    contributions=None,
    joint_bank_ready=False,
    joint_payment_method=None,
    process_url,
    transactions_url,
    sign_url,
    failed_url,
    csrf_token,
    phone_number='',
):
    breakdown_data = []
    for row in joint_breakdown or []:
        member = row.get('member')
        breakdown_data.append({
            'member_name': member.full_name,
            'member_id': str(member.id),
            'share_percentage': str(member.share_percentage),
            'amount': str(row.get('amount', '0')),
            'phone_number': member.phone_number,
        })

    contribution_data = []
    for contribution in contributions or []:
        contribution_data.append({
            'member_name': contribution.member.full_name if contribution.member else 'Leader / Full Amount',
            'amount': str(contribution.amount),
            'channel': contribution.get_payment_channel_display() if hasattr(contribution, 'get_payment_channel_display') else contribution.payment_channel,
            'status': contribution.get_status_display() if hasattr(contribution, 'get_status_display') else contribution.status,
            'phone_number': contribution.phone_number,
            'bank_reference': contribution.bank_reference,
            'depositor_name': contribution.depositor_name,
        })

    group = transaction.joint_group if transaction.is_joint_purchase and transaction.joint_group else None
    return {
        'transaction_id': str(transaction.id),
        'parcel_number': transaction.land_parcel.parcel_number,
        'seller_email': transaction.seller.email,
        'buyer_email': transaction.buyer.email,
        'agreed_price': str(transaction.agreed_price),
        'is_joint_purchase': bool(transaction.is_joint_purchase),
        'joint_group_name': group.name if group else None,
        'joint_group_ownership': group.get_ownership_type_display() if group else None,
        'joint_payment_method': group.get_preferred_payment_method_display() if group else None,
        'joint_bank_ready': bool(joint_bank_ready),
        'breakdown': breakdown_data,
        'contributions': contribution_data,
        'phone_number': phone_number,
        'csrf_token': csrf_token,
        'process_url': process_url,
        'transactions_url': transactions_url,
        'sign_url': sign_url,
        'failed_url': failed_url,
        'default_payment_method': 'joint_bank_account' if group and group.preferred_payment_method == 'Joint_Bank_Account' else 'm_pesa',
        'bank_name': group.bank_name if group else None,
        'bank_account_name': group.bank_account_name if group else None,
        'bank_account_number': group.bank_account_number if group else None,
        'bank_branch': group.bank_branch if group else None,
    }


def serialize_recommendations_page(recommended, rec_type, popular_parcels, popular_county, recently_viewed, user=None):
    def _serialize_parcels(parcels):
        return [serialize_parcel(parcel, user) for parcel in parcels]

    recommended_data = []
    for parcel, score in recommended or []:
        item = serialize_parcel(parcel, user)
        item['match_score'] = score
        recommended_data.append(item)

    return {
        'rec_type': rec_type,
        'recommended': recommended_data,
        'popular_county': popular_county,
        'popular_parcels': _serialize_parcels(popular_parcels or []),
        'recently_viewed': _serialize_parcels(recently_viewed or []),
    }


def serialize_prediction_result(result):
    if not result:
        return None
    if result.get('error'):
        return {'error': result['error']}

    comparisons = [
        {
            'county': comparison.get('county', ''),
            'constituency': comparison.get('constituency', ''),
            'land_use': comparison.get('land_use', ''),
            'size_acres': str(comparison.get('size_acres', '')),
            'price_per_acre': str(comparison.get('price_per_acre', '')),
        }
        for comparison in result.get('comparisons', [])
    ]

    model_accuracy = result.get('model_accuracy', '')
    try:
        model_accuracy = f"{float(model_accuracy) * 100:.1f}%"
    except (TypeError, ValueError):
        model_accuracy = str(model_accuracy)

    return {
        'county': result.get('county'),
        'land_use': result.get('land_use'),
        'size_acres': str(result.get('size_acres', '')),
        'price_per_acre': str(result.get('price_per_acre', '')),
        'total_value': str(result.get('total_value', '')),
        'confidence_low': str(result.get('confidence_low', '')),
        'confidence_high': str(result.get('confidence_high', '')),
        'model_accuracy': model_accuracy,
        'comparisons': comparisons,
    }


def serialize_law(law):
    return {
        'title': law['title'],
        'citation': law['citation'],
        'applies_to': law['applies_to'],
        'summary': law['summary'],
        'official_url': law['official_url'],
        'required': law.get('required', False),
    }


def serialize_joint_member(member):
    return {
        'id': str(member.id),
        'full_name': member.full_name,
        'share_percentage': str(member.share_percentage),
        'phone_number': member.phone_number,
        'email': member.email,
        'id_number': member.id_number,
        'kra_pin': member.kra_pin,
        'is_leader': member.is_leader,
        'has_signed': member.has_signed,
        'signature_status': 'Signed' if member.has_signed else 'Pending',
        'edit_url': reverse('frontend:edit_joint_member', args=[member.id]),
        'delete_url': reverse('frontend:delete_joint_member', args=[member.id]),
    }


def serialize_joint_group(group):
    members = [serialize_joint_member(member) for member in group.members.all()]
    return {
        'id': str(group.id),
        'name': group.name,
        'group_type': group.get_group_type_display(),
        'ownership_type': group.get_ownership_type_display(),
        'preferred_payment_method': group.preferred_payment_method,
        'bank_name': group.bank_name,
        'bank_account_name': group.bank_account_name,
        'bank_account_number': group.bank_account_number,
        'bank_branch': group.bank_branch,
        'total_share': str(group.total_share),
        'is_valid': group.is_valid,
        'members': members,
        'detail_url': reverse('frontend:joint_group_detail', args=[group.id]),
        'edit_url': reverse('frontend:edit_joint_group', args=[group.id]),
        'laws_url': reverse('frontend:joint_laws'),
    }


def serialize_messages(request):
    return [{'level': message.level_tag, 'text': str(message)} for message in get_messages(request)]


def serialize_message_thread(partner, messages, user):
    return {
        'partner': serialize_user(partner),
        'latest_timestamp': messages[0].timestamp.strftime('%b %d, %Y') if messages else '',
        'count': len(messages),
        'messages': [
            {
                'id': str(message.id),
                'sender_email': message.sender.email,
                'content': message.content,
                'timestamp': message.timestamp.strftime('%b %d, %Y %H:%M'),
                'is_self': getattr(message.sender, 'id', None) == getattr(user, 'id', None),
            }
            for message in messages
        ],
    }


def serialize_support_ticket(ticket):
    return {
        'id': str(ticket.id),
        'subject': ticket.subject,
        'message_excerpt': ticket.message[:160] + ('...' if len(ticket.message) > 160 else ''),
        'status': ticket.status,
        'created_at': ticket.created_at.strftime('%b %d, %Y') if getattr(ticket, 'created_at', None) else '',
    }


def _field_type(bound_field):
    widget = bound_field.field.widget
    if isinstance(widget, django_forms.Textarea):
        return 'textarea'
    if isinstance(widget, django_forms.Select):
        return 'select'
    if isinstance(widget, django_forms.RadioSelect):
        return 'radio'
    if isinstance(widget, django_forms.CheckboxInput):
        return 'checkbox'
    if isinstance(widget, django_forms.ClearableFileInput):
        return 'file'
    input_type = getattr(widget, 'input_type', 'text') or 'text'
    if input_type == 'password':
        return 'password'
    if input_type == 'email':
        return 'email'
    if input_type == 'number':
        return 'number'
    if input_type == 'tel':
        return 'tel'
    if input_type == 'url':
        return 'url'
    if input_type == 'hidden':
        return 'hidden'
    return 'text'


def _serialize_bound_field(bound_field):
    field = bound_field.field
    widget = field.widget
    field_type = _field_type(bound_field)
    attrs = getattr(widget, 'attrs', {}) or {}
    value = bound_field.value()
    if value is None:
        value = ''
    if isinstance(value, (list, tuple)):
        value = ','.join(str(item) for item in value)
    value = str(value)

    options = None
    if field_type in {'select', 'radio'} and getattr(field, 'choices', None):
        options = [
            {
                'value': str(choice_value),
                'label': str(choice_label),
                'selected': str(choice_value) == value,
                'disabled': False,
            }
            for choice_value, choice_label in field.choices
        ]

    return {
        'name': bound_field.html_name,
        'label': bound_field.label or bound_field.name.replace('_', ' ').title(),
        'type': field_type,
        'value': value,
        'checked': bool(bound_field.value()) if field_type == 'checkbox' else None,
        'placeholder': attrs.get('placeholder'),
        'helpText': str(field.help_text) if field.help_text else None,
        'required': bool(field.required),
        'disabled': bool(field.disabled),
        'rows': int(attrs.get('rows', 4)) if field_type == 'textarea' else None,
        'min': attrs.get('min'),
        'max': attrs.get('max'),
        'step': attrs.get('step'),
        'accept': attrs.get('accept'),
        'options': options,
        'errors': [str(error) for error in bound_field.errors],
        'autoFocus': bool(attrs.get('autofocus')),
    }


def _serialize_hidden_field(bound_field):
    value = bound_field.value()
    return {
        'name': bound_field.html_name,
        'value': '' if value is None else str(value),
    }


def serialize_form(form, *, action, submit_label, method='post', cancel_label=None, cancel_href=None, intro=None, sections=None):
    fields = [_serialize_bound_field(bound_field) for bound_field in form.visible_fields()]
    hidden_fields = [_serialize_hidden_field(bound_field) for bound_field in form.hidden_fields()]
    data = {
        'action': action,
        'method': method,
        'enctype': 'multipart/form-data' if form.is_multipart() else 'application/x-www-form-urlencoded',
        'submitLabel': submit_label,
        'cancelLabel': cancel_label,
        'cancelHref': cancel_href,
        'intro': intro,
        'hiddenFields': hidden_fields,
        'errors': [str(error) for error in form.non_field_errors()],
    }

    if sections:
        by_name = {field['name']: field for field in fields}
        grouped = []
        used = set()
        for section in sections:
            section_fields = []
            for name in section.get('fields', []):
                if name in by_name:
                    section_fields.append(by_name[name])
                    used.add(name)
            grouped.append({
                'title': section.get('title'),
                'subtitle': section.get('subtitle'),
                'fields': section_fields,
            })
        remainder = [field for field in fields if field['name'] not in used]
        if remainder:
            grouped.append({'fields': remainder})
        data['sections'] = grouped
    else:
        data['fields'] = fields

    return data


def serialize_formset(formset, *, action, submit_label, method='post', intro=None):
    rows = []
    for index, form in enumerate(formset.forms):
        rows.append({
            'index': index,
            'fields': [_serialize_bound_field(bound_field) for bound_field in form.visible_fields()],
            'hiddenFields': [_serialize_hidden_field(bound_field) for bound_field in form.hidden_fields()],
        })

    return {
        'action': action,
        'method': method,
        'enctype': 'multipart/form-data' if formset.is_multipart() else 'application/x-www-form-urlencoded',
        'submitLabel': submit_label,
        'intro': intro,
        'managementFields': [_serialize_hidden_field(bound_field) for bound_field in formset.management_form.hidden_fields()],
        'formsetRows': rows,
        'errors': [str(error) for error in formset.non_form_errors()],
    }
