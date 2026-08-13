"""
Common Event Registry

Maps an event to one or more handlers.
"""

from .constants import *

EVENT_REGISTRY = {

    # =====================================================
    # Assignment Created
    # =====================================================

    (
        EMISSION,
        ASSIGNMENT,
        ASSIGNED,
    ): [
        NOTIFICATION,
        TIMESHEET,
        EMAIL,
    ],

    # =====================================================
    # Assignee Submitted
    # =====================================================

    (
        EMISSION,
        ASSIGNMENT,
        SUBMITTED,
    ): [
        NOTIFICATION,
        EMAIL,
    ],

    # =====================================================
    # Reviewer Approved
    # =====================================================

    (
        EMISSION,
        ASSIGNMENT,
        REVIEW_APPROVED,
    ): [
        NOTIFICATION,
        EMAIL,
    ],

    # =====================================================
    # Reviewer Rejected
    # =====================================================

    (
        EMISSION,
        ASSIGNMENT,
        REVIEW_REJECTED,
    ): [
        NOTIFICATION,
        EMAIL,
    ],

    # =====================================================
    # Final Approved
    # =====================================================

    (
        EMISSION,
        ASSIGNMENT,
        FINAL_APPROVED,
    ): [
        NOTIFICATION,
        EMAIL,
    ],

    # =====================================================
    # Final Rejected
    # =====================================================

    (
        EMISSION,
        ASSIGNMENT,
        FINAL_REJECTED,
    ): [
        NOTIFICATION,
        EMAIL,
    ],

}