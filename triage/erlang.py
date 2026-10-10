"""Erlang-C (M/M/c) triage queue model (spec section 2.2).

arrivals lambda (patients/hour), c nurses each serving mu = 60 / intake_minutes patients/hour.
    offered load  u   = lambda / mu
    utilization   rho = u / c           (must be < 1 or the queue grows without bound)
    P(wait > 0)   = C(c, u)             (Erlang C)
    mean wait     Wq  = C / (c*mu - lambda)

C is computed through the Erlang-B recursion, which stays stable for large c.
These inputs (28 arrivals/hour, 4 nurses, 8 and 3.5 minute intake) are the spec's modeling
assumptions, not measurements. Note: the spec's printed 34.8 minute wait is not what this formula
gives; the correct figure for its own inputs is about 25.7 minutes (HACKATHON_TEST_DRIVE.md section 4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_ARRIVALS_PER_HOUR = 28.0
DEFAULT_NURSES = 4
DEFAULT_MANUAL_MINUTES = 8.0
DEFAULT_AUTOMATED_MINUTES = 3.5


@dataclass(frozen=True)
class QueueMetrics:
    arrivals_per_hour: float
    intake_minutes: float
    nurses: int
    service_rate_per_hour: float
    utilization: float
    stable: bool
    prob_wait: float          # 1.0 when unstable
    wait_minutes: float       # math.inf when unstable

    @property
    def wait_seconds(self) -> float:
        return self.wait_minutes * 60.0


def _validate(arrivals_per_hour: float, intake_minutes: float, nurses: int) -> None:
    if arrivals_per_hour <= 0:
        raise ValueError("arrivals_per_hour must be positive")
    if intake_minutes <= 0:
        raise ValueError("intake_minutes must be positive")
    if int(nurses) != nurses or nurses < 1:
        raise ValueError("nurses must be a whole number of at least 1")


def erlang_c_probability(offered_load: float, servers: int) -> float:
    """P(an arriving patient has to wait) for offered load u = lambda/mu and c servers. Requires u < c."""
    if offered_load >= servers:
        return 1.0
    b = 1.0  # Erlang B(0, u)
    for k in range(1, servers + 1):
        b = offered_load * b / (k + offered_load * b)
    rho = offered_load / servers
    return b / (1.0 - rho * (1.0 - b))


def queue_metrics(arrivals_per_hour: float, intake_minutes: float, nurses: int) -> QueueMetrics:
    _validate(arrivals_per_hour, intake_minutes, nurses)
    mu = 60.0 / intake_minutes
    u = arrivals_per_hour / mu
    rho = u / nurses
    if rho >= 1.0:
        return QueueMetrics(arrivals_per_hour, intake_minutes, int(nurses), mu, rho, False, 1.0, math.inf)
    p_wait = erlang_c_probability(u, int(nurses))
    wq_hours = p_wait / (nurses * mu - arrivals_per_hour)
    return QueueMetrics(arrivals_per_hour, intake_minutes, int(nurses), mu, rho, True, p_wait, wq_hours * 60.0)


def max_stable_intake_minutes(arrivals_per_hour: float, nurses: int) -> float:
    """Slowest intake at which the queue is still stable (utilization = 100%)."""
    _validate(arrivals_per_hour, 1.0, nurses)
    return nurses * 60.0 / arrivals_per_hour


def wait_curve(arrivals_per_hour: float, nurses: int, intake_minutes: list[float]) -> list[float]:
    """Mean wait in minutes for each intake time (math.inf where the queue is unstable)."""
    return [queue_metrics(arrivals_per_hour, m, nurses).wait_minutes for m in intake_minutes]


def spec_scenarios(
    arrivals_per_hour: float = DEFAULT_ARRIVALS_PER_HOUR,
    nurses: int = DEFAULT_NURSES,
    manual_minutes: float = DEFAULT_MANUAL_MINUTES,
    automated_minutes: float = DEFAULT_AUTOMATED_MINUTES,
) -> dict:
    """The spec's two scenarios and the reduction between them."""
    manual = queue_metrics(arrivals_per_hour, manual_minutes, nurses)
    automated = queue_metrics(arrivals_per_hour, automated_minutes, nurses)
    reduction = None
    if manual.stable and automated.stable and manual.wait_minutes > 0:
        reduction = 1.0 - automated.wait_minutes / manual.wait_minutes
    return {"manual": manual, "automated": automated, "wait_reduction": reduction}
