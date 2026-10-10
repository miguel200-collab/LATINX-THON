"""Asymmetric safety loss gate (spec section 2.1 / 4.2).

Tier numbers follow ESI: 1 is the most urgent, 5 the least.
Predicting tier i when the true tier is j costs:
    0                       if i == j
    c_over  * |i - j|       if i <  j   (over-triage: sent to a more urgent tier than needed)
    c_under * |i - j|       if i >  j   (under-triage: sent to a less urgent tier than needed)
The suggested review tier is the i with the lowest expected loss under the model's probabilities.
It is a safety flag for the nurse. It is not an assigned ESI.
"""

from __future__ import annotations

import numpy as np

NUM_TIERS = 5


def loss_matrix(c_under: float = 10.0, c_over: float = 1.0) -> np.ndarray:
    """L[i-1, j-1] = cost of predicting tier i when the true tier is j."""
    tiers = np.arange(1, NUM_TIERS + 1)
    diff = tiers[:, None] - tiers[None, :]  # predicted - true
    return np.where(diff > 0, c_under * diff, np.where(diff < 0, c_over * -diff, 0.0))


def calculate_safest_esi(
    probabilities: list[float],
    c_under: float = 10.0,
    c_over: float = 1.0,
) -> dict:
    """Evaluate expected clinical loss over a 5-tier ESI probability distribution.

    probabilities: P(ESI 1) .. P(ESI 5). Normalized if they do not sum to 1.
    Ties go to the more urgent tier (the safer choice).
    """
    probs = np.asarray(probabilities, dtype=float)
    if probs.shape != (NUM_TIERS,):
        raise ValueError(f"Expected {NUM_TIERS} probabilities (ESI 1 to 5), got {probs.size}.")
    if np.any(probs < 0) or not np.all(np.isfinite(probs)):
        raise ValueError("Probabilities must be finite and non-negative.")
    total = probs.sum()
    if total <= 0:
        raise ValueError("Probabilities must not all be zero.")
    if not np.isclose(total, 1.0):
        probs = probs / total

    expected = loss_matrix(c_under, c_over) @ probs  # expected[i-1] = sum_j p_j * L(i, j)
    raw_tier = int(np.argmax(probs) + 1)
    optimal_tier = int(np.argmin(expected) + 1)
    return {
        "probabilities": [float(p) for p in probs],
        "raw_argmax_tier": raw_tier,
        "optimal_safety_tier": optimal_tier,
        "expected_losses": [float(x) for x in expected],
        "override_triggered": optimal_tier < raw_tier,
    }
