"""Verification tests for the review-gated content pipeline."""

from pathlib import Path
import tempfile
import unittest

from src.content_pipeline import ContentPipeline, ContentRequest, PipelineError
from src.knowledge_base import KnowledgeBase


class ContentPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
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
            self.assertEqual(len(list(Path(temporary_directory).iterdir())), 1)

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


if __name__ == "__main__":
    unittest.main()
