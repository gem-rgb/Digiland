"""
Email utilities for Digiland system
"""
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def _public_backend_base_url():
    """Return the browser-visible backend origin used in emails."""
    return getattr(settings, "PUBLIC_BACKEND_URL", "").strip().rstrip("/") or "http://127.0.0.1:8000"


def send_agent_approval_email(agent):
    """Send approval email to agent"""
    subject = "Your Agent Application Has Been Approved - Digiland"
    
    context = {
        'agent': agent,
        'login_url': f"{_public_backend_base_url()}/staff/login/"
    }
    
    html_message = render_to_string('emails/agent_approval.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        from core.services.notifications import NotificationService
        NotificationService.send_email(
            user=agent,
            notification_type="AGENT_APPLICATION_APPROVED",
            subject=subject,
            html_body=html_message,
            text_body=plain_message,
            action_url=context.get('login_url', ''),
        )
    except Exception:
        pass

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[agent.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True, "Approval email sent successfully"
    except Exception as e:
        return False, f"Failed to send approval email: {str(e)}"


def send_agent_rejection_email(agent):
    """Send rejection email to agent"""
    subject = "Your Agent Application Status - Digiland"
    
    context = {
        'agent': agent,
    }
    
    html_message = render_to_string('emails/agent_rejection.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        from core.services.notifications import NotificationService
        NotificationService.send_email(
            user=agent,
            notification_type="AGENT_APPLICATION_REJECTED",
            subject=subject,
            html_body=html_message,
            text_body=plain_message,
        )
    except Exception:
        pass

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[agent.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True, "Rejection email sent successfully"
    except Exception as e:
        return False, f"Failed to send rejection email: {str(e)}"


def send_task_assignment_email(agent, parcel):
    """Send task assignment email to agent"""
    subject = f"New Task Assignment - {parcel.parcel_number}"
    
    context = {
        'agent': agent,
        'parcel': parcel,
        'dashboard_url': f"{_public_backend_base_url()}/agent/dashboard/"
    }
    
    html_message = render_to_string('emails/task_assignment.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        from core.services.notifications import NotificationService
        NotificationService.send_email(
            user=agent,
            notification_type="TASK_ASSIGNED",
            subject=subject,
            html_body=html_message,
            text_body=plain_message,
            action_url=context.get('dashboard_url', ''),
        )
    except Exception:
        pass

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[agent.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True, "Task assignment email sent successfully"
    except Exception as e:
        return False, f"Failed to send task assignment email: {str(e)}"


def send_user_approval_email(user):
    """Send approval email to buyer/seller"""
    subject = "Your Identity Has Been Verified - Digiland"
    
    context = {
        'user': user,
        'login_url': f"{_public_backend_base_url()}/accounts/login/"
    }
    
    html_message = render_to_string('emails/user_approval.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        from core.services.notifications import NotificationService
        NotificationService.send_email(
            user=user,
            notification_type="USER_KYC_VERIFIED",
            subject=subject,
            html_body=html_message,
            text_body=plain_message,
            action_url=context.get('login_url', ''),
        )
    except Exception:
        pass

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],

            html_message=html_message,
            fail_silently=False,
        )
        return True, "User approval email sent successfully"
    except Exception as e:
        return False, f"Failed to send user approval email: {str(e)}"


def send_agent_rating_notification(agent, rating, review):
    """Send rating notification to agent"""
    subject = f"Performance Update - {rating} Star Rating Received"
    
    context = {
        'agent': agent,
        'rating': rating,
        'review': review,
        'dashboard_url': f"{_public_backend_base_url()}/agent/dashboard/"
    }
    
    html_message = render_to_string('emails/agent_rating.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[agent.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True, "Rating notification email sent successfully"
    except Exception as e:
        return False, f"Failed to send rating notification: {str(e)}"


def send_custom_email(recipients, subject, message, html_message=None):
    """Send custom email to multiple recipients"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients if isinstance(recipients, list) else [recipients],
            html_message=html_message,
            fail_silently=False,
        )
        return True, "Email sent successfully"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"
