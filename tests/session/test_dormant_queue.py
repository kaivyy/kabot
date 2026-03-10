from kabot.session.manager import Session


def test_dormant_queue_enqueue_and_drain_by_session():
    from kabot.core.queue import DormantQueue

    queue = DormantQueue()

    queue.enqueue("telegram:123", {"role": "user", "content": "halo"})
    queue.enqueue("discord:456", {"role": "user", "content": "hello"})

    assert queue.has_pending("telegram:123") is True
    assert queue.has_pending("discord:456") is True
    assert queue.drain("telegram:123") == [{"role": "user", "content": "halo"}]
    assert queue.has_pending("telegram:123") is False
    assert queue.drain("telegram:123") == []
    assert queue.has_pending("discord:456") is True


def test_session_pending_work_round_trip():
    session = Session(key="telegram:123")

    session.enqueue_pending_work({"kind": "user_turn", "content": "tolong lanjutkan"})
    session.enqueue_pending_work({"kind": "retry", "reason": "network_drop"})

    assert session.has_pending_work() is True
    assert session.metadata["pending_work"] == [
        {"kind": "user_turn", "content": "tolong lanjutkan"},
        {"kind": "retry", "reason": "network_drop"},
    ]

    drained = session.drain_pending_work()

    assert drained == [
        {"kind": "user_turn", "content": "tolong lanjutkan"},
        {"kind": "retry", "reason": "network_drop"},
    ]
    assert session.has_pending_work() is False
    assert "pending_work" not in session.metadata
