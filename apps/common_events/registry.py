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

    # =====================================================
    # Goal Created
    # =====================================================

    (
        GOALS,
        GOAL,
        CREATED,
    ): [
        EMAIL,
    ],

        # =====================================================
    # Goal KPI At Risk
    # =====================================================

    (
        GOALS,
        GOAL,
        KPI_AT_RISK,
    ): [
        EMAIL,
    ],

    # =====================================================
    # Goal KPI Critical
    # =====================================================

    (
        GOALS,
        GOAL,
        KPI_CRITICAL,
    ): [
        EMAIL,
    ],

    # =====================================================
    # Goal KPI Near Target
    # =====================================================

    (
        GOALS,
        GOAL,
        KPI_NEAR_TARGET,
    ): [
        EMAIL,
    ],

    # =====================================================
    # Goal KPI Target Achieved
    # =====================================================

    (
        GOALS,
        GOAL,
        KPI_TARGET_ACHIEVED,
    ): [
        EMAIL,
    ],


}