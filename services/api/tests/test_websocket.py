import pytest

from api.websocket import parse_client_message, SubscribeAction, UnsubscribeAction, SubscribeAllAction


def test_parse_subscribe():
    msg = parse_client_message('{"action":"subscribe","equipment_ids":["E-01","E-02"]}')
    assert isinstance(msg, SubscribeAction)
    assert msg.equipment_ids == ["E-01", "E-02"]


def test_parse_unsubscribe():
    msg = parse_client_message('{"action":"unsubscribe","equipment_ids":["E-01"]}')
    assert isinstance(msg, UnsubscribeAction)
    assert msg.equipment_ids == ["E-01"]


def test_parse_subscribe_all():
    msg = parse_client_message('{"action":"subscribe_all"}')
    assert isinstance(msg, SubscribeAllAction)


def test_parse_invalid_json():
    with pytest.raises(ValueError, match="invalid json"):
        parse_client_message("not json")


def test_parse_unknown_action():
    with pytest.raises(ValueError, match="unknown action"):
        parse_client_message('{"action":"nope"}')
