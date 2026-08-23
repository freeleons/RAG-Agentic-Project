from server.utils import content_hash


def test_content_hash_is_deterministic():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})


def test_content_hash_differs_for_different_content():
    assert content_hash({"a": 1}) != content_hash({"a": 2})


def test_content_hash_none_in_none_out():
    assert content_hash(None) is None


def test_content_hash_accepts_plain_strings():
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("world")
