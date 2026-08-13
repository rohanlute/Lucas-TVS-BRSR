"""
Common Event Registry

Maps an event to one or more handlers.
"""

from .constants import *

EVENT_REGISTRY = {

    # =====================================================
    # EMISSION
    # =====================================================

    (
        EMISSION,
        ASSIGNMENT,
        ASSIGNED,
    ): [
        NOTIFICATION,
        TIMESHEET,
    ],

    (
        EMISSION,
        ASSIGNMENT,
        SUBMITTED,
    ): [
        NOTIFICATION,
        TIMESHEET,
    ],

    (
        EMISSION,
        ASSIGNMENT,
        REVIEW_APPROVED,
    ): [
        NOTIFICATION,
        TIMESHEET,
    ],

    (
        EMISSION,
        ASSIGNMENT,
        REVIEW_REJECTED,
    ): [
        NOTIFICATION,
        TIMESHEET,
    ],

    (
        EMISSION,
        ASSIGNMENT,
        FINAL_APPROVED,
    ): [
        NOTIFICATION,
        TIMESHEET,
    ],

    (
        EMISSION,
        ASSIGNMENT,
        FINAL_REJECTED,
    ): [
        NOTIFICATION,
        TIMESHEET,
    ],

}