import tempfile
import unittest
from pathlib import Path

from humungousaur.collectors.envelope import CollectorEventEnvelope
from humungousaur.collectors.event_log import CollectorEventLog


class CollectorEventLogTests(unittest.TestCase):
    def test_event_log_appends_reads_and_acks_consumer_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log = CollectorEventLog(Path(tmp_dir) / "collector_events.sqlite3")
            first = log.append(_event("one"))
            second = log.append(_event("two"))
            batch = log.read_batch("attention_batch", limit=10)
            log.ack("attention_batch", second["sequence"])
            after_ack = log.read_batch("attention_batch", limit=10)
            status = log.status()

        self.assertTrue(first["inserted"])
        self.assertTrue(second["inserted"])
        self.assertEqual([event["text"] for event in batch], ["event one", "event two"])
        self.assertEqual(after_ack, [])
        self.assertEqual(status["event_count"], 2)
        self.assertEqual(status["consumer_offsets"][0]["consumer_name"], "attention_batch")

    def test_event_log_retries_then_dead_letters_and_advances_offset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log = CollectorEventLog(Path(tmp_dir) / "collector_events.sqlite3")
            appended = log.append(_event("failure"))
            sequence = appended["sequence"]
            first = log.retry_later("memory", sequence, "temporary failure")
            second = log.retry_later("memory", sequence, "still failing", max_attempts=2)
            status = log.status()
            remaining = log.read_batch("memory", limit=10)

        self.assertFalse(first["dead_lettered"])
        self.assertTrue(second["dead_lettered"])
        self.assertEqual(status["dead_letter_count"], 1)
        self.assertEqual(remaining, [])

    def test_event_log_waits_until_retry_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log = CollectorEventLog(Path(tmp_dir) / "collector_events.sqlite3")
            appended = log.append(_event("retry"))
            log.retry_later("memory", appended["sequence"], "temporary failure")
            remaining = log.read_batch("memory", limit=10)

        self.assertEqual(remaining, [])

    def test_event_log_persists_consumer_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log = CollectorEventLog(Path(tmp_dir) / "collector_events.sqlite3")
            log.save_consumer_state("attention_batch", {"pending_attention_events": [{"collector": "filesystem"}]})
            state = log.consumer_state("attention_batch")

        self.assertEqual(state["pending_attention_events"][0]["collector"], "filesystem")

    def test_event_log_validates_event_envelopes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log = CollectorEventLog(Path(tmp_dir) / "collector_events.sqlite3")
            event = _event("invalid")
            event.stimulus_type = "not_a_filesystem_stimulus"

            with self.assertRaises(ValueError):
                log.append(event)

    def test_event_log_queries_and_records_helper_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log = CollectorEventLog(Path(tmp_dir) / "collector_events.sqlite3")
            log.append(_event("one"))
            log.append(_event("two"))
            log.record_helper_health(
                helper_id="macos-fsevents",
                collector="filesystem",
                platform="Darwin",
                status="running",
                pid=123,
                version="0.1",
                permission_state="granted",
                metadata={"watch_count": 2},
            )
            events = log.query(collector="filesystem", stimulus_type="file_modified", limit=10)
            status = log.status()

        self.assertEqual(len(events), 2)
        self.assertEqual(status["helper_health"][0]["helper_id"], "macos-fsevents")
        self.assertEqual(status["helper_health"][0]["metadata"]["watch_count"], 2)

    def test_event_log_retention_prunes_acked_overflow_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            log = CollectorEventLog(Path(tmp_dir) / "collector_events.sqlite3")
            last_sequence = 0
            for index in range(1005):
                last_sequence = log.append(_event(f"retention-{index}"))["sequence"]
            first_retention = log.enforce_retention(max_events=1000)
            log.ack("memory", last_sequence)
            log.ack("attention_batch", last_sequence)
            second_retention = log.enforce_retention(max_events=1000)
            status = log.status()

        self.assertEqual(first_retention["deleted"], 0)
        self.assertEqual(second_retention["deleted"], 5)
        self.assertEqual(status["event_count"], 1000)


def _event(name: str) -> CollectorEventEnvelope:
    return CollectorEventEnvelope(
        event_id=f"event-{name}",
        collector="filesystem",
        source="activity",
        platform="Darwin",
        stimulus_type="file_modified",
        privacy_tier="metadata",
        occurred_at="2026-06-11T00:00:00+00:00",
        received_at="2026-06-11T00:00:00+00:00",
        signature=f"filesystem:file_modified:{name}",
        text=f"event {name}",
        metadata={},
        payload={},
        redaction={
            "raw_content_included": False,
            "attention_safe": True,
            "payload_compacted_before_llm": True,
        },
    )


if __name__ == "__main__":
    unittest.main()
