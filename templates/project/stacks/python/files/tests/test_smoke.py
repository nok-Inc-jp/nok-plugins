from __PACKAGE__ import hello


def test_hello() -> None:
    assert hello("ノック") == "こんにちは、ノック"
