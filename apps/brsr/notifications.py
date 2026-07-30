from apps.email_master.services import EmailService
from django.urls import reverse
from django.contrib.sites.shortcuts import get_current_site
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def _recipient_email(actor):
    """assignee/reviewer are GenericForeignKeys — could be User, Plant, etc.
    Only actual User objects have an email worth sending to."""
    return getattr(actor, "email", None)


def _get_assignment_url(assignment, request=None):
    """
    Generate the full URL for an assignment.
    
    Args:
        assignment: The assignment object
        request: Optional request object for building absolute URLs
        
    Returns:
        str: The assignment URL
    """
    # Build the relative URL path
    # Note: You may need to adjust this based on your actual URL structure
    relative_url = f"/brsr/workspace/section_b/?assignment_id={assignment.id}"
    
    if request:
        # Build absolute URL using request
        try:
            domain = get_current_site(request).domain
            protocol = 'https' if request.is_secure() else 'http'
            return f"{protocol}://{domain}{relative_url}"
        except Exception as e:
            logger.warning(f"Could not build absolute URL from request: {e}")
    
    # Fallback: Use settings or just return relative URL
    if hasattr(settings, 'SITE_URL'):
        return f"{settings.SITE_URL}{relative_url}"
    
    return relative_url


def notify_assignment_created(assignment, request=None):
    """
    Send notification when a new assignment is created.
    
    Args:
        assignment: The assignment object
        request: Optional request object for building absolute URLs
    """
    recipient = assignment.assignee
    
    # Debug logging
    logger.info(f"=== EMAIL DEBUG: notify_assignment_created ===")
    logger.info(f"Assignment ID: {assignment.assignment_id}")
    logger.info(f"Recipient: {recipient}")
    logger.info(f"Recipient type: {type(recipient)}")
    logger.info(f"Recipient email: {getattr(recipient, 'email', None)}")
    
    if not _recipient_email(recipient):
        logger.warning(f"Skipping email: No email for recipient {recipient}")
        return
    
    # Generate assignment URL
    assignment_url = _get_assignment_url(assignment, request)
    
    try:
        # Log what we're sending
        logger.info(f"Sending email to: {getattr(recipient, 'email', None)}")
        logger.info(f"Subject: New BRSR assignment: {assignment.assignment_id}")
        
        EmailService.send_email(
            recipient=recipient,
            subject=f"New BRSR assignment: {assignment.assignment_id}",
            message=(
                f"Hello,\n\n"
                f"A new BRSR assignment has been created for you.\n\n"
                f"Assignment: {assignment.assignment_id}\n"
                f"Plant: {assignment.plant.name}\n"
                f"Section: {assignment.section.name}\n"
                f"Financial Year: {assignment.financial_year}\n"
                f"Due Date: {assignment.due_date or 'Not set'}\n\n"
                f"Please log in to review and complete it.\n"
                f"\nView assignment: {assignment_url}"
            ),
            html_template="emails/brsr/assignment_created.html",
            context={
                "assignment": assignment,
                "assignment_url": assignment_url,
            },
        )
        logger.info("Email sent successfully for assignment_created")
    except Exception as e:
        logger.error(f"Failed to send assignment_created email: {e}", exc_info=True)


def notify_assignment_submitted(assignment, next_assignee, request=None):
    """
    Send notification when an assignment is submitted.
    
    Args:
        assignment: The assignment object
        next_assignee: The next person in the workflow
        request: Optional request object for building absolute URLs
    """
    if not next_assignee or not _recipient_email(next_assignee):
        logger.info(f"Skipping email: No next assignee or no email for {next_assignee}")
        return
    
    # Generate assignment URL
    assignment_url = _get_assignment_url(assignment, request)
    
    try:
        logger.info(f"Sending submission notification to: {getattr(next_assignee, 'email', None)}")
        logger.info(f"Assignment: {assignment.assignment_id}, Stage: {assignment.workflow_stage_label}")
        
        EmailService.send_email(
            recipient=next_assignee,
            subject=f"BRSR assignment awaiting action: {assignment.assignment_id}",
            message=(
                f"Assignment {assignment.assignment_id} has been submitted and is "
                f"now awaiting your action at the '{assignment.workflow_stage_label}' stage.\n\n"
                f"View assignment: {assignment_url}"
            ),
            html_template="emails/brsr/assignment_submitted.html",
            context={
                "assignment": assignment,
                "assignment_url": assignment_url,
            },
        )
        logger.info("Email sent successfully for assignment_submitted")
    except Exception as e:
        logger.error(f"Failed to send assignment_submitted email: {e}", exc_info=True)


def notify_assignment_approved(assignment, request=None):
    """
    Send notification when an assignment is approved.
    
    Args:
        assignment: The assignment object
        request: Optional request object for building absolute URLs
    """
    recipient = assignment.assigner
    
    if not _recipient_email(recipient):
        logger.info(f"Skipping email: No email for assigner {recipient}")
        return
    
    # Generate assignment URL
    assignment_url = _get_assignment_url(assignment, request)
    
    try:
        logger.info(f"Sending approval notification to: {getattr(recipient, 'email', None)}")
        logger.info(f"Assignment: {assignment.assignment_id} approved")
        
        EmailService.send_email(
            recipient=recipient,
            subject=f"BRSR assignment approved: {assignment.assignment_id}",
            message=(
                f"Assignment {assignment.assignment_id} has been fully approved.\n\n"
                f"View assignment: {assignment_url}"
            ),
            html_template="emails/brsr/assignment_approved.html",
            context={
                "assignment": assignment,
                "assignment_url": assignment_url,
            },
        )
        logger.info("Email sent successfully for assignment_approved")
    except Exception as e:
        logger.error(f"Failed to send assignment_approved email: {e}", exc_info=True)


def notify_assignment_rejected(assignment, remark, request=None):
    """
    Send notification when an assignment is rejected.
    
    Args:
        assignment: The assignment object
        remark: The rejection reason/remark
        request: Optional request object for building absolute URLs
    """
    recipient = assignment.assignee
    
    if not _recipient_email(recipient):
        logger.info(f"Skipping email: No email for assignee {recipient}")
        return
    
    # Generate assignment URL
    assignment_url = _get_assignment_url(assignment, request)
    
    try:
        logger.info(f"Sending rejection notification to: {getattr(recipient, 'email', None)}")
        logger.info(f"Assignment: {assignment.assignment_id} rejected")
        
        EmailService.send_email(
            recipient=recipient,
            subject=f"BRSR assignment rejected: {assignment.assignment_id}",
            message=(
                f"Assignment {assignment.assignment_id} was rejected and returned "
                f"to you for correction.\n\nReviewer remark: {remark}\n\n"
                f"View assignment: {assignment_url}"
            ),
            html_template="emails/brsr/assignment_rejected.html",
            context={
                "assignment": assignment,
                "remark": remark,
                "assignment_url": assignment_url,
            },
        )
        logger.info("Email sent successfully for assignment_rejected")
    except Exception as e:
        logger.error(f"Failed to send assignment_rejected email: {e}", exc_info=True)


# Optional: Helper function to test email sending
def test_email_notifications(assignment, request=None):
    """
    Helper function to test all email notifications for an assignment.
    
    Args:
        assignment: The assignment object
        request: Optional request object
    """
    logger.info("=== Testing all email notifications ===")
    
    # Test assignment created
    logger.info("Testing: notify_assignment_created")
    notify_assignment_created(assignment, request)
    
    # Test assignment submitted (if there's a next assignee)
    if hasattr(assignment, 'next_assignee'):
        logger.info("Testing: notify_assignment_submitted")
        notify_assignment_submitted(assignment, assignment.next_assignee, request)
    
    # Test assignment approved
    logger.info("Testing: notify_assignment_approved")
    notify_assignment_approved(assignment, request)
    
    # Test assignment rejected
    logger.info("Testing: notify_assignment_rejected")
    notify_assignment_rejected(assignment, "Test rejection remark", request)
    
    logger.info("=== Email testing complete ===")