"""Temporary probe for the M0.5 CI gate: this test must fail on purpose."""


def test_deliberately_failing_probe() -> None:
    assert False, "M0.5: remove this test to make CI pass"
