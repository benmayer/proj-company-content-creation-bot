"""Verification tests for the feedback store and its storage backends."""

from pathlib import Path
import tempfile
import unittest

from src.feedback_store import (
    APPROVED,
    DECLINED,
    FeedbackStore,
    FeedbackStoreError,
    FileBackend,
    clean_draft,
)


def _record(store: FeedbackStore, outcome: str, draft: str = "d", reason: str = "", channel: str = "X", kind: str = "reply"):
    return store.record(outcome, channel, kind, "topic", draft, reason)


class FeedbackSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = FeedbackStore(FileBackend(Path(self.directory.name) / "feedback.jsonl"))

    def test_empty_store_renders_placeholder(self) -> None:
        self.assertIn("No learned feedback yet", self.store.select("X", "reply").render())

    def test_latest_first_and_limits(self) -> None:
        for number in range(4):
            _record(self.store, APPROVED, draft=f"approved {number}")
            _record(self.store, DECLINED, reason=f"reason {number}")
        learned = self.store.select("X", "reply", approved_limit=2, declined_limit=3)
        self.assertEqual([e.draft for e in learned.approved], ["approved 3", "approved 2"])
        self.assertEqual([e.reason for e in learned.declined], ["reason 3", "reason 2", "reason 1"])

    def test_matches_channel_and_type_case_insensitively(self) -> None:
        _record(self.store, DECLINED, reason="match", channel="Linkedin", kind="Reply")
        _record(self.store, DECLINED, reason="other channel", channel="X", kind="reply")
        _record(self.store, DECLINED, reason="other type", channel="LinkedIn", kind="meme")
        learned = self.store.select("LinkedIn", "reply")
        self.assertEqual([e.reason for e in learned.declined], ["match"])

    def test_malformed_lines_are_skipped(self) -> None:
        _record(self.store, DECLINED, reason="kept")
        self.store.backend.append("not json")
        self.store.backend.append('{"unexpected": 1}')
        self.assertEqual(len(self.store.events()), 1)

    def test_lines_from_older_versions_still_load(self) -> None:
        self.store.backend.append(
            '{"outcome": "declined", "channel": "X", "content_type": "post_update", "product": "flights", '
            '"topic": "t", "draft": "d", "reason": "old reason", "created_at": "2026-10-01T00:00:00+00:00"}'
        )
        self.assertEqual([e.reason for e in self.store.select("X", "post").declined], ["old reason"])

    def test_approved_example_drops_review_notes_and_is_truncated(self) -> None:
        _record(self.store, APPROVED, draft="Good post\n\nHUMAN REVIEW NOTES\n- check fares")
        rendered = self.store.select("X", "reply").render()
        self.assertIn("Good post", rendered)
        self.assertNotIn("check fares", rendered)
        _record(self.store, APPROVED, draft="x" * 5000)
        self.assertLess(len(self.store.select("X", "reply", approved_limit=1).render()), 1200)

    def test_example_cleanup_handles_markdown_formatting(self) -> None:
        draft = "**Post Draft for Instagram:**\n\nGood post 😅\n\n---\n\n**HUMAN REVIEW NOTES:**\n1. check"
        _record(self.store, APPROVED, draft=draft)
        rendered = self.store.select("X", "reply").render()
        self.assertTrue(rendered.endswith("1. Good post 😅"), rendered)

    def test_clean_draft_strips_label_and_notes_but_keeps_the_message(self) -> None:
        for raw in (
            "**Post draft**\n\nSee you at the gate.",
            "Post type draft:\nSee you at the gate.\n\nHUMAN REVIEW NOTES\n- x",
            "## Draft\n\nSee you at the gate.\n\n---\n**HUMAN REVIEW NOTES:**\n1. x",
        ):
            self.assertEqual(clean_draft(raw), "See you at the gate.", raw)
        self.assertEqual(clean_draft("Draft your bags early:\nand fly."), "Draft your bags early:\nand fly.")
        self.assertEqual(clean_draft('"pack light, fly cheap."'), "pack light, fly cheap.")
        self.assertEqual(clean_draft('"a" is not "b"'), '"a" is not "b"')

    def test_unknown_outcome_is_rejected(self) -> None:
        with self.assertRaises(FeedbackStoreError):
            _record(self.store, "maybe")


class BackendTests(unittest.TestCase):
    def test_events_survive_a_new_store_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "feedback.jsonl"
            _record(FeedbackStore(FileBackend(path)), DECLINED, reason="survives restart")
            reloaded = FeedbackStore(FileBackend(path))  # new process, same disk
            self.assertEqual(reloaded.select("X", "reply").declined[0].reason, "survives restart")

    def test_from_env_prefers_configured_path(self) -> None:
        default = Path("outputs/feedback.jsonl")
        self.assertEqual(FeedbackStore.from_env(default, {}).backend.path, default)
        disk = FeedbackStore.from_env(default, {"FEEDBACK_STORE_PATH": "/var/data/feedback.jsonl"})
        self.assertEqual(disk.backend.path, Path("/var/data/feedback.jsonl"))


if __name__ == "__main__":
    unittest.main()
