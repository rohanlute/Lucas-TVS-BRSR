"""
Common Event Constants

This file contains only constants.

No business logic should be added here.
"""

# =====================================================
# Modules
# =====================================================

EMISSION = "EMISSION"
BRSR = "BRSR"
GOALS = "GOALS"

# =====================================================
# Entities
# =====================================================

ASSIGNMENT = "ASSIGNMENT"
QUESTION = "QUESTION"
GOAL = "GOAL"

# =====================================================
# Actions
# =====================================================

CREATED = "CREATED"
UPDATED = "UPDATED"

# Goal KPI Status
KPI_AT_RISK = "KPI_AT_RISK"
KPI_CRITICAL = "KPI_CRITICAL"
KPI_NEAR_TARGET = "KPI_NEAR_TARGET"
KPI_TARGET_ACHIEVED = "KPI_TARGET_ACHIEVED"

# Assignment Lifecycle
ASSIGNED = "ASSIGNED"
SUBMITTED = "SUBMITTED"

# Reviewer Stage
REVIEW_APPROVED = "REVIEW_APPROVED"
REVIEW_REJECTED = "REVIEW_REJECTED"

# Coordinator / Final Approval Stage
FINAL_APPROVED = "FINAL_APPROVED"
FINAL_REJECTED = "FINAL_REJECTED"

# Workflow
COMPLETED = "COMPLETED"
PAUSED = "PAUSED"
RESUMED = "RESUMED"

# =====================================================
# Handlers
# =====================================================

NOTIFICATION = "notification"
TIMESHEET = "timesheet"
EMAIL = "email"
AUDIT = "audit"