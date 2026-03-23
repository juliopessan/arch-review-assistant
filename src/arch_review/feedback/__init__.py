"""Feedback loop system — immune system layer for arch-review.

Implements the approve/reject feedback pattern from Module 09:
  - Per-domain JSON files (security, reliability, cost, ...)
  - FIFO 30 entries max (context window safety)
  - Agents consult before suggesting to avoid repeating rejected patterns
  - Every 30 reviews: feedback → lessons consolidation
"""
from arch_review.feedback.store import FeedbackStore, FeedbackEntry, FeedbackDecision

__all__ = ["FeedbackStore", "FeedbackEntry", "FeedbackDecision"]
