from datetime import datetime

from parking.rules import METERED, NO_PARKING, TIME_LIMIT, Rule, evaluate

MON_FRI = frozenset(range(5))
MON_9AM = datetime(2026, 11, 2, 9, 0)  # a Monday


def test_free_when_no_rules_apply():
    assert evaluate([], MON_9AM, 120).legal


def test_no_parking_window_blocks():
    r = Rule(NO_PARKING, days=MON_FRI, start_min=7 * 60, end_min=9 * 60)
    v = evaluate([r], datetime(2026, 11, 2, 8, 0), 60)
    assert not v.legal and v.illegal_from == datetime(2026, 11, 2, 8, 0)


def test_stay_ending_before_no_parking_is_fine():
    r = Rule(NO_PARKING, days=MON_FRI, start_min=7 * 60, end_min=9 * 60)
    assert evaluate([r], datetime(2026, 11, 2, 6, 0), 60).legal


def test_metered_cost_and_limit():
    r = Rule(METERED, days=MON_FRI, start_min=8 * 60, end_min=18 * 60, limit_min=120, price_per_hour=4.0)
    ok = evaluate([r], MON_9AM, 90)
    assert ok.legal and ok.cost == 6.0 and ok.move_by == datetime(2026, 11, 2, 11, 0)
    over = evaluate([r], MON_9AM, 180)
    assert not over.legal and over.illegal_from == datetime(2026, 11, 2, 11, 0)


def test_free_now_reports_when_charging_starts():
    r = Rule(METERED, days=MON_FRI, start_min=8 * 60, end_min=18 * 60, price_per_hour=2.0)
    v = evaluate([r], datetime(2026, 11, 2, 19, 0), 60)
    assert v.legal and v.cost == 0 and v.charging_starts == datetime(2026, 11, 3, 8, 0)


def test_limit_that_outlasts_window_is_not_a_violation():
    r = Rule(TIME_LIMIT, days=MON_FRI, start_min=8 * 60, end_min=10 * 60, limit_min=120)
    assert evaluate([r], datetime(2026, 11, 2, 9, 30), 240).legal
