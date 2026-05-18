"""v4 capture extraction boundary.

The extractor returns candidates only. Reconciliation decides which candidates
are safe to apply and which must become reviewable suggestions.
"""


def extract_capture_candidates(content, mode="auto"):
    """Return extraction candidates for a captured note.

    Cycle 7 keeps this boundary deliberately small and mockable. Real model
    integration can be added behind this function without changing capture
    reconciliation semantics.
    """
    return {}
