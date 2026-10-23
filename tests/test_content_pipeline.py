"""Verification tests for the review-gated content pipeline."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from src.content_pipeline import ContentPipeline, ContentRequest, PipelineError
from src.knowledge_base import KnowledgeBase


class ContentPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        # Keep tests on local temp files even if the developer has FEEDBACK_STORE_PATH set.
        env = {key: value for key, value in os.environ.items() if not key.startswith("FEEDBACK_")}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.knowledge_base = KnowledgeBase.load()
        self.request = ContentRequest("social_post", "Ryanair", "summer travel")

    def test_approval_saves_timestamped_output(self) -> None:
        calls = []

        def generator(prompt: str, client: object = None) -> str:
            calls.append(prompt)
            return "Approved draft"

        with tempfile.TemporaryDirectory() as temporary_directory:
            pipeline = ContentPipeline(self.knowledge_base, temporary_directory, generator)
            result = pipeline.run(self.request, approve=lambda _draft: True)
            self.assertTrue(result.output_path.is_file())
            self.assertEqual(result.output_path.parent, Path(temporary_directory))
            self.assertIn("approved: true", result.output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(calls), 1)
            self.assertIn("PRIMARY CONTEXT", calls[0])
            self.assertIn("SECONDARY CONTEXT", calls[0])

    def test_rejection_requests_iteration_and_saves_only_approved_draft(self) -> None:
        drafts = iter(("first draft", "revised draft"))
        prompts = []

        def generator(prompt: str, client: object = None) -> str:
            prompts.append(prompt)
            return next(drafts)

        with tempfile.TemporaryDirectory() as temporary_directory:
            pipeline = ContentPipeline(self.knowledge_base, temporary_directory, generator)
            approvals = iter((False, True))
            result = pipeline.run(
                self.request,
                approve=lambda _draft: next(approvals),
                feedback=lambda _draft: "Make it more concise.",
            )
            self.assertEqual(result.draft, "revised draft")
            self.assertEqual(result.iterations, 2)
            self.assertIn("Make it more concise.", prompts[1])
            self.assertEqual(len(list(Path(temporary_directory).glob("*.md"))), 1)

    def test_rejection_without_feedback_does_not_save(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pipeline = ContentPipeline(
                self.knowledge_base,
                temporary_directory,
                lambda _prompt, client=None: "draft",
            )
            with self.assertRaisesRegex(PipelineError, "feedback"):
                pipeline.run(self.request, approve=lambda _draft: False)
            self.assertEqual(list(Path(temporary_directory).iterdir()), [])

    def test_decline_is_recorded_without_saving_an_approved_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pipeline = ContentPipeline(self.knowledge_base, temporary_directory, lambda _prompt, client=None: "draft")
            event = pipeline.record_decline(self.request, "Needs a different angle.", "rejected draft")
            self.assertEqual(event.outcome, "declined")
            feedback_file = Path(temporary_directory) / "feedback.jsonl"
            self.assertIn("Needs a different angle.", feedback_file.read_text(encoding="utf-8"))
            self.assertEqual(list(Path(temporary_directory).glob("*.md")), [])


class SelfLearningTests(unittest.TestCase):
    def setUp(self) -> None:
        env = {key: value for key, value in os.environ.items() if not key.startswith("FEEDBACK_")}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.knowledge_base = KnowledgeBase.load()
        self.request = ContentRequest(
            "reply", "flights", "reply: summer sale", channel="X"
        )

    def _pipeline(self, directory: str) -> ContentPipeline:
        return ContentPipeline(self.knowledge_base, directory, lambda _prompt, client=None: "Short punchy draft\n\nHUMAN REVIEW NOTES\n- check")

    def test_prompt_changes_after_approval_and_decline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self._pipeline(directory)
            context = pipeline.monitor(self.request)
            before = pipeline.brief(self.request, context)
            self.assertIn("No learned feedback yet", before)

            pipeline.publish(self.request, "Short punchy draft\n\nHUMAN REVIEW NOTES\n- check", 1)
            pipeline.record_decline(self.request, "Too formal for X.", "Dear customers, ...")
            after = pipeline.brief(self.request, context)

            self.assertNotEqual(before, after)
            self.assertIn("Short punchy draft", after)
            self.assertIn("Too formal for X.", after)
            self.assertNotIn("Dear customers", after)  # only the reason is fed back for declines
            self.assertNotIn("HUMAN REVIEW NOTES\n- check", after.split("LEARNED FEEDBACK — ")[1].split("FORMAT LIMITS")[0])

    def test_feedback_only_applies_to_same_channel_and_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self._pipeline(directory)
            pipeline.record_decline(self.request, "Too formal for X.")
            context = pipeline.monitor(self.request)
            other_channel = ContentRequest("reply", "flights", "reply: summer sale", channel="LinkedIn")
            other_type = ContentRequest("meme", "flights", "meme: summer sale", channel="X")
            self.assertIn("No learned feedback yet", pipeline.brief(other_channel, context))
            self.assertIn("No learned feedback yet", pipeline.brief(other_type, context))
            self.assertIn("Too formal for X.", pipeline.brief(self.request, context))

    def test_learned_feedback_is_separate_from_company_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self._pipeline(directory)
            pipeline.record_decline(self.request, "UNIQUE-REASON-MARKER")
            prompt = pipeline.brief(self.request, pipeline.monitor(self.request))
            primary = prompt.split("PRIMARY CONTEXT")[1].split("SECONDARY CONTEXT")[0]
            secondary = prompt.split("SECONDARY CONTEXT")[1].split("VOICE RULES")[0]
            learned = prompt.split("LEARNED FEEDBACK — ")[1]
            self.assertNotIn("UNIQUE-REASON-MARKER", primary + secondary)
            self.assertIn("UNIQUE-REASON-MARKER", learned)
            self.assertIn("NOT company facts", prompt)


if __name__ == "__main__":
    unittest.main()
