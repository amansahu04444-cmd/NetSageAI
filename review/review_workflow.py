"""
NetSage AI - Review Data Model & State Transition Module

Defines the data model and state transition rules for Human-in-the-Loop review:
States: PENDING -> ACCEPTED | MODIFIED | REJECTED
Immutability: Original AI diagnosis is NEVER overwritten or mutated.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, Field
from ai.structured_output import DiagnosisResult

ReviewStatusType = Literal["PENDING", "ACCEPTED", "MODIFIED", "REJECTED"]


class InvalidStateTransitionError(Exception):
    """Raised when an illegal review state transition is attempted."""
    pass


class ReviewValidationError(Exception):
    """Raised when mandatory review fields (like reviewer or reason) are missing."""
    pass


class ReviewRecord(BaseModel):
    review_id: str = Field(default_factory=lambda: f"REV-{uuid.uuid4().hex[:6].upper()}")
    case_id: str
    status: ReviewStatusType = "PENDING"
    ai_diagnosis: DiagnosisResult
    human_diagnosis: Optional[DiagnosisResult] = None
    reviewer: Optional[str] = None
    reason: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reviewed_at: Optional[str] = None

    def accept(self, reviewer: str, reason: Optional[str] = None) -> "ReviewRecord":
        """Transitions PENDING review to ACCEPTED."""
        if self.status != "PENDING":
            raise InvalidStateTransitionError(
                f"Cannot accept review '{self.review_id}': current state is '{self.status}'. "
                "Only PENDING reviews can be accepted."
            )
        if not reviewer or not reviewer.strip():
            raise ReviewValidationError("Accepting a review requires a valid reviewer name.")

        self.status = "ACCEPTED"
        self.reviewer = reviewer.strip()
        self.reason = reason.strip() if reason and reason.strip() else "Approved as presented."
        self.human_diagnosis = self.ai_diagnosis.model_copy(deep=True)
        self.reviewed_at = datetime.now(timezone.utc).isoformat()
        return self

    def modify(self, edited_diagnosis: DiagnosisResult, reviewer: str, reason: str) -> "ReviewRecord":
        """Transitions PENDING review to MODIFIED with human-edited diagnosis and reason."""
        if self.status != "PENDING":
            raise InvalidStateTransitionError(
                f"Cannot modify review '{self.review_id}': current state is '{self.status}'. "
                "Only PENDING reviews can be modified."
            )
        if not reviewer or not reviewer.strip():
            raise ReviewValidationError("Modifying a review requires a valid reviewer name.")
        if not reason or not reason.strip():
            raise ReviewValidationError("Modifying a review requires a valid reason explaining the changes.")
        if not edited_diagnosis:
            raise ReviewValidationError("Modifying a review requires an edited human diagnosis.")

        self.status = "MODIFIED"
        self.reviewer = reviewer.strip()
        self.reason = reason.strip()
        self.human_diagnosis = edited_diagnosis.model_copy(deep=True)
        self.reviewed_at = datetime.now(timezone.utc).isoformat()
        return self

    def reject(self, reviewer: str, reason: str) -> "ReviewRecord":
        """Transitions PENDING review to REJECTED with mandatory reason."""
        if self.status != "PENDING":
            raise InvalidStateTransitionError(
                f"Cannot reject review '{self.review_id}': current state is '{self.status}'. "
                "Only PENDING reviews can be rejected."
            )
        if not reviewer or not reviewer.strip():
            raise ReviewValidationError("Rejecting a review requires a valid reviewer name.")
        if not reason or not reason.strip():
            raise ReviewValidationError("Rejecting a review requires a valid reason explaining the rejection.")

        self.status = "REJECTED"
        self.reviewer = reviewer.strip()
        self.reason = reason.strip()
        self.human_diagnosis = None
        self.reviewed_at = datetime.now(timezone.utc).isoformat()
        return self
