import pytest

from dba_agent.schemas import QA, Category
from dba_agent.state import SessionNotFound, SessionStore, Stage


def test_create_save_load_roundtrip(tmp_path):
    store = SessionStore(tmp_path)
    s = store.create("  A small library system.  ")
    assert s.brief == "A small library system." and s.stage == Stage.INTAKE

    s.stage = Stage.INTERVIEW
    s.interview.qa.append(QA(round=1, category=Category.RULES, question="Q?", answer="A."))
    store.save(s)

    loaded = store.load(s.id)
    assert loaded.stage == Stage.INTERVIEW
    assert loaded.interview.qa[0].answer == "A."
    assert not (store.dir(s.id) / "session.json.tmp").exists()  # atomic write cleaned up


def test_ids_are_unique_and_latest_is_last(tmp_path):
    store = SessionStore(tmp_path)
    a, b = store.create("one"), store.create("two")
    assert a.id != b.id
    assert [s.id for s in store.list()] == [a.id, b.id]
    assert store.latest_id() == b.id


def test_missing_session_raises(tmp_path):
    with pytest.raises(SessionNotFound):
        SessionStore(tmp_path).load("nope")


def test_empty_store(tmp_path):
    store = SessionStore(tmp_path / "does-not-exist")
    assert store.list() == [] and store.latest_id() is None
