"""Deterministic parking rules engine. Models read signs into Rule objects; this code decides."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

NO_PARKING, NO_STOPPING, PERMIT, TIME_LIMIT, METERED = (
    "no_parking", "no_stopping", "permit", "time_limit", "metered",
)
ALL_DAYS = frozenset(range(7))  # Monday=0
STEP = timedelta(minutes=1)


@dataclass(frozen=True)
class Rule:
    kind: str
    days: frozenset = ALL_DAYS
    start_min: int = 0        # minutes after midnight
    end_min: int = 24 * 60
    limit_min: int | None = None
    price_per_hour: float = 0.0
    note: str = ""

    def active(self, t: datetime) -> bool:
        minute = t.hour * 60 + t.minute
        return t.weekday() in self.days and self.start_min <= minute < self.end_min


@dataclass
class Verdict:
    legal: bool
    cost: float = 0.0
    move_by: datetime | None = None
    illegal_from: datetime | None = None
    charging_starts: datetime | None = None
    reasons: list = field(default_factory=list)


def _window_end(rule: Rule, t: datetime) -> datetime:
    end = t
    while rule.active(end):
        end += STEP
    return end


def evaluate(rules: list[Rule], arrive: datetime, minutes: int) -> Verdict:
    stay_end = arrive + timedelta(minutes=minutes)
    v = Verdict(legal=True)
    blocking = {NO_PARKING, NO_STOPPING, PERMIT}

    t = arrive
    while t < stay_end:
        for r in rules:
            if r.kind in blocking and r.active(t):
                v.legal = False
                v.illegal_from = v.illegal_from or t
                v.reasons.append(f"{r.kind.replace('_', ' ')} at {t:%a %H:%M}")
        metered = [r for r in rules if r.kind == METERED and r.active(t)]
        if metered:
            v.cost += max(r.price_per_hour for r in metered) / 60
        t += STEP

    if not any(r.kind == METERED and r.active(arrive) for r in rules):
        t = arrive
        horizon = arrive + timedelta(days=7)
        while t < horizon:
            if any(r.kind == METERED and r.active(t) for r in rules):
                v.charging_starts = t
                break
            t += STEP

    for r in rules:
        if r.kind in (TIME_LIMIT, METERED) and r.limit_min and r.active(arrive):
            deadline = arrive + timedelta(minutes=r.limit_min)
            if deadline < _window_end(r, arrive):
                v.move_by = min(v.move_by, deadline) if v.move_by else deadline
                if stay_end > deadline:
                    v.legal = False
                    v.illegal_from = min(v.illegal_from or deadline, deadline)
                    v.reasons.append(f"{r.limit_min}-minute limit ends {deadline:%H:%M}")

    v.cost = round(v.cost, 2)
    return v
