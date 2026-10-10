"""Erlang-C checks (HACKATHON_TEST_DRIVE.md section 4). The spec's 34.8 minute figure is wrong; 25.7 is right."""

import math

import pytest

from triage import charts
from triage.erlang import (
    erlang_c_probability,
    max_stable_intake_minutes,
    queue_metrics,
    spec_scenarios,
    wait_curve,
)


def textbook_erlang_c(c, u):
    """Independent factorial formula straight from the spec (used only to cross-check)."""
    rho = u / c
    top = (u**c / math.factorial(c)) / (1 - rho)
    return top / (sum(u**k / math.factorial(k) for k in range(c)) + top)


def test_manual_intake_matches_corrected_spec_numbers():
    m = queue_metrics(28, 8.0, 4)
    assert m.service_rate_per_hour == pytest.approx(7.5)
    assert m.utilization == pytest.approx(0.9333, abs=1e-4)
    assert m.prob_wait == pytest.approx(0.856, abs=0.001)
    assert m.wait_minutes == pytest.approx(25.7, abs=0.1)     # NOT the spec's 34.8


def test_automated_intake_matches_spec_numbers():
    m = queue_metrics(28, 3.5, 4)
    assert m.service_rate_per_hour == pytest.approx(17.142857, abs=1e-4)
    assert m.utilization == pytest.approx(0.408, abs=0.001)
    assert m.prob_wait == pytest.approx(0.096, abs=0.001)
    assert m.wait_minutes == pytest.approx(0.14, abs=0.01)    # about 9 seconds; spec says 0.12
    assert m.wait_seconds < 10


def test_reduction_is_about_99_percent():
    s = spec_scenarios()
    assert s["wait_reduction"] == pytest.approx(0.994, abs=0.003)


def test_single_server_probability_of_waiting_equals_utilization():
    for rho in (0.1, 0.5, 0.9):
        assert erlang_c_probability(rho, 1) == pytest.approx(rho)


@pytest.mark.parametrize("c,u", [(2, 1.5), (4, 3.7333), (6, 5.0), (10, 8.5)])
def test_recursion_agrees_with_the_textbook_formula(c, u):
    assert erlang_c_probability(u, c) == pytest.approx(textbook_erlang_c(c, u), rel=1e-9)


def test_wait_grows_as_intake_gets_slower():
    waits = wait_curve(28, 4, [2.0, 3.5, 5.0, 6.5, 8.0, 8.4])
    assert waits == sorted(waits)
    assert waits[-1] > 5 * waits[0]


def test_unstable_queue_is_reported_not_hidden():
    limit = max_stable_intake_minutes(28, 4)
    assert limit == pytest.approx(8.5714, abs=1e-3)
    m = queue_metrics(28, 9.0, 4)
    assert m.stable is False and math.isinf(m.wait_minutes) and m.prob_wait == 1.0
    assert queue_metrics(28, limit, 4).stable is False        # exactly 100% utilization
    assert spec_scenarios(manual_minutes=9.0)["wait_reduction"] is None


def test_more_nurses_means_less_waiting():
    assert queue_metrics(28, 8.0, 5).wait_minutes < queue_metrics(28, 8.0, 4).wait_minutes


@pytest.mark.parametrize("args", [(0, 8, 4), (28, 0, 4), (28, 8, 0), (28, 8, 2.5), (-1, 8, 4)])
def test_bad_inputs_raise(args):
    with pytest.raises(ValueError):
        queue_metrics(*args)


def test_queue_chart_has_the_curve_and_both_scenarios():
    fig = charts.queue_chart(28, 4, 8.0, 3.5)
    names = [t.name for t in fig.data]
    assert "Mean queue wait" in names and "Manual intake" in names and "Automated intake" in names
    assert any("25.7" in (t.text or [""])[0] for t in fig.data if t.name == "Manual intake")


def test_queue_chart_handles_an_unstable_scenario():
    fig = charts.queue_chart(28, 4, 9.5, 3.5)
    assert any("never clears" in (t.name or "") for t in fig.data)


def test_probability_and_loss_charts_highlight_the_suggested_tier():
    fig = charts.probability_chart([0.02, 0.18, 0.6, 0.15, 0.05], suggested_tier=2, most_likely_tier=3)
    assert list(fig.data[0].marker.color).count("#b91c1c") == 1 and fig.data[0].marker.color[1] == "#b91c1c"
    fig2 = charts.loss_chart([2.03, 1.25, 2.45, 10.25, 19.7], suggested_tier=2)
    assert fig2.data[0].marker.color[1] == "#b91c1c"
