"""Acceptance checks for the loss gate (HACKATHON_TEST_DRIVE.md section 4)."""

import pytest

from triage.loss import calculate_safest_esi, loss_matrix


def test_ankle_sprain_stays_at_esi_4():
    r = calculate_safest_esi([0, 0.05, 0, 0.95, 0])
    assert r["raw_argmax_tier"] == 4
    assert r["optimal_safety_tier"] == 4
    assert r["override_triggered"] is False
    assert r["expected_losses"][3] == pytest.approx(1.0)   # keep ESI 4
    assert r["expected_losses"][1] == pytest.approx(1.9)   # escalate to ESI 2
    assert r["expected_losses"] == pytest.approx([2.9, 1.9, 1.45, 1.0, 11.0])


def test_ambiguous_epigastric_escalates_to_esi_2():
    r = calculate_safest_esi([0, 0.20, 0, 0.80, 0])
    assert r["raw_argmax_tier"] == 4
    assert r["optimal_safety_tier"] == 2
    assert r["override_triggered"] is True
    assert r["expected_losses"][1] == pytest.approx(1.6)
    assert r["expected_losses"][3] == pytest.approx(4.0)
    assert r["expected_losses"] == pytest.approx([2.6, 1.6, 2.8, 4.0, 14.0])


def test_spec_sample_most_likely_3_safest_2():
    r = calculate_safest_esi([0.02, 0.18, 0.60, 0.15, 0.05])
    assert r["raw_argmax_tier"] == 3
    assert r["optimal_safety_tier"] == 2
    assert r["override_triggered"] is True
    assert r["expected_losses"] == pytest.approx([2.03, 1.25, 2.45, 10.25, 19.7])


def test_unnormalized_probabilities_are_normalized():
    a = calculate_safest_esi([2, 18, 60, 15, 5])
    b = calculate_safest_esi([0.02, 0.18, 0.60, 0.15, 0.05])
    assert a["optimal_safety_tier"] == b["optimal_safety_tier"]
    assert a["expected_losses"] == pytest.approx(b["expected_losses"])
    assert sum(a["probabilities"]) == pytest.approx(1.0)


@pytest.mark.parametrize("tier", [1, 2, 3, 4, 5])
def test_all_mass_on_one_tier_returns_that_tier(tier):
    probs = [0.0] * 5
    probs[tier - 1] = 1.0
    r = calculate_safest_esi(probs)
    assert r["raw_argmax_tier"] == tier
    assert r["optimal_safety_tier"] == tier
    assert r["override_triggered"] is False
    assert r["expected_losses"][tier - 1] == pytest.approx(0.0)


def test_two_tier_crossover_is_about_nine_percent_not_fifteen():
    """ESI 4 vs ESI 2: escalate once P(ESI 2) > 2/22 (about 9.1%). The spec's '15%' is wrong."""
    just_below = calculate_safest_esi([0, 0.09, 0, 0.91, 0])
    just_above = calculate_safest_esi([0, 0.092, 0, 0.908, 0])
    assert just_below["optimal_safety_tier"] == 4
    assert just_above["optimal_safety_tier"] == 2
    # A 12% case is already escalated, which a 15% threshold would have missed.
    assert calculate_safest_esi([0, 0.12, 0, 0.88, 0])["optimal_safety_tier"] == 2


def test_ties_go_to_the_more_urgent_tier():
    r = calculate_safest_esi([0.5, 0, 0, 0, 0.5], c_under=1.0, c_over=1.0)
    assert r["optimal_safety_tier"] <= 3


def test_loss_matrix_shape_and_asymmetry():
    m = loss_matrix()
    assert m.shape == (5, 5)
    assert m[3, 1] == 20.0   # predict ESI 4 when truth is ESI 2: under-triage, 10 x 2
    assert m[1, 3] == 2.0    # predict ESI 2 when truth is ESI 4: over-triage, 1 x 2
    assert (m.diagonal() == 0).all()


@pytest.mark.parametrize(
    "bad",
    [[0.2, 0.2, 0.2, 0.2], [0, 0, 0, 0, 0], [-0.1, 0.5, 0.2, 0.2, 0.2], [float("nan"), 0, 0, 0, 1]],
)
def test_bad_input_raises(bad):
    with pytest.raises(ValueError):
        calculate_safest_esi(bad)
