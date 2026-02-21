"""Tests for cron delivery mode resolution."""

from kabot.cron.delivery import resolve_delivery_plan
from kabot.cron.types import CronDeliveryConfig, CronJob, CronPayload, CronSchedule


class TestResolveDeliveryPlan:
    def test_announce_mode(self):
        job = CronJob(
            id="j1",
            name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi"),
            delivery=CronDeliveryConfig(mode="announce", channel="telegram", to="123"),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "announce"
        assert plan["channel"] == "telegram"
        assert plan["to"] == "123"

    def test_webhook_mode(self):
        job = CronJob(
            id="j2",
            name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi"),
            delivery=CronDeliveryConfig(
                mode="webhook",
                webhook_url="https://example.com/hook",
            ),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "webhook"
        assert plan["webhook_url"] == "https://example.com/hook"

    def test_none_mode(self):
        job = CronJob(
            id="j3",
            name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi"),
            delivery=CronDeliveryConfig(mode="none"),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "none"
        assert plan["channel"] is None
        assert plan["to"] is None

    def test_legacy_deliver_true(self):
        job = CronJob(
            id="j4",
            name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi", deliver=True, channel="telegram", to="123"),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "announce"
        assert plan["channel"] == "telegram"

    def test_legacy_deliver_false(self):
        job = CronJob(
            id="j5",
            name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi", deliver=False),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "none"
