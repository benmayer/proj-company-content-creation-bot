"""Verification tests for the review-gated content pipeline."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from src.content_pipeline import (
    CANNOT_READ_SCREENSHOT,
    ContentPipeline,
    ContentRequest,
    PipelineError,
    is_link_only,
    request_problem,
)
from src.knowledge_base import KnowledgeBase

PNG = b"\x89PNG\r\n\x1a\n-not-a-real-image"


def _clean_env(test: unittest.TestCase) -> None:
    # Keep tests on local temp files even if the developer has FEEDBACK_STORE_PATH set.
    env = {key: value for key, value in os.environ.items() if not key.startswith("FEEDBACK_")}
    patcher = mock.patch.dict(os.environ, env, clear=True)
    patcher.start()
    test.addCleanup(patcher.stop)


class ContentPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        _clean_env(self)
        self.knowledge_base = KnowledgeBase.load()
        self.request = ContentRequest("post", "summer travel", "X")

    def test_approval_saves_timestamped_output(self) -> None:
        calls = []

        def generator(prompt: str, client: object = None, **_: object) -> str:
            calls.append(prompt)
            return "Approved draft"

        with tempfile.TemporaryDirectory() as temporary_directory:
            pipeline = ContentPipeline(self.knowledge_base, temporary_directory, generator)
            result = pipeline.run(self.request, approve=lambda _draft: True)
            self.assertTrue(result.output_path.is_file())
            self.assertEqual(result.output_path.parent, Path(temporary_directory))
            saved = result.output_path.read_text(encoding="utf-8")
            self.assertIn("approved: true", saved)
            self.assertNotIn("product", saved)
            self.assertEqual(len(calls), 1)
            self.assertIn("PRIMARY CONTEXT", calls[0])
            self.assertIn("SECONDARY CONTEXT", calls[0])

    def test_draft_is_only_the_message(self) -> None:
        raw = "**Post draft**\n\nSee you at the gate.\n\n---\n\n**HUMAN REVIEW NOTES**\n- check"
        with tempfile.TemporaryDirectory() as temporary_directory:
            pipeline = ContentPipeline(self.knowledge_base, temporary_directory, lambda _prompt, **_: raw)
            result = pipeline.run(self.request, approve=lambda _draft: True)
            self.assertEqual(result.draft, "See you at the gate.")
            self.assertEqual(pipeline.draft(self.request, result.selected_context), "See you at the gate.")

    def test_system_prompt_and_temperature_reach_the_generator(self) -> None:
        received = {}

        def generator(prompt: str, client: object = None, **kwargs: object) -> str:
            received.update(kwargs, prompt=prompt)
            return "ok"

        with tempfile.TemporaryDirectory() as temporary_directory:
            pipeline = ContentPipeline(self.knowledge_base, temporary_directory, generator)
            pipeline.draft(self.request, pipeline.monitor(self.request))
        self.assertIn("You write Ryanair's content", received["system"])
        self.assertNotIn("You write Ryanair's content", received["prompt"])
        self.assertEqual(received["temperature"], 0.9)
        self.assertEqual(received["images"], ())

    def test_topic_only_request_has_no_product_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pipeline = ContentPipeline(self.knowledge_base, temporary_directory)
            prompt = pipeline.brief(self.request, pipeline.monitor(self.request))
        self.assertIn("Topic: summer travel", prompt)
        self.assertNotIn("product", prompt.lower())

    def test_rejection_requests_iteration_and_saves_only_approved_draft(self) -> None:
        drafts = iter(("first draft", "revised draft"))
        prompts = []

        def generator(prompt: str, client: object = None, **_: object) -> str:
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
            pipeline = ContentPipeline(self.knowledge_base, temporary_directory, lambda _prompt, **_: "draft")
            with self.assertRaisesRegex(PipelineError, "feedback"):
                pipeline.run(self.request, approve=lambda _draft: False)
            self.assertEqual(list(Path(temporary_directory).iterdir()), [])

    def test_decline_is_recorded_without_saving_an_approved_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            pipeline = ContentPipeline(self.knowledge_base, temporary_directory, lambda _prompt, **_: "draft")
            event = pipeline.record_decline(self.request, "Needs a different angle.", "rejected draft")
            self.assertEqual(event.outcome, "declined")
            feedback_file = Path(temporary_directory) / "feedback.jsonl"
            self.assertIn("Needs a different angle.", feedback_file.read_text(encoding="utf-8"))
            self.assertEqual(list(Path(temporary_directory).glob("*.md")), [])


class RequestValidationTests(unittest.TestCase):
    def test_link_only_detection(self) -> None:
        self.assertTrue(is_link_only("https://x.com/someone/status/123"))
        self.assertTrue(is_link_only("look https://x.com/someone/status/123"))
        self.assertFalse(is_link_only("why are bag fees so high https://x.com/a/1"))
        self.assertFalse(is_link_only("why are bag fees so high?"))

    def test_problems_are_reported_in_plain_words(self) -> None:
        cases = [
            (ContentRequest("reply", channel="X", original_content="https://x.com/a/status/1"), "Links can't be opened"),
            (ContentRequest("reply", channel="X"), "Paste the post"),
            (ContentRequest("post", "", "X"), "Enter a topic"),
            (ContentRequest("press_release", "news", "X"), "X does not offer press release"),
            (ContentRequest("reply", channel="LinkedIn", original_content="hello there friends"), "does not offer reply"),
            (ContentRequest("post", "news", "Myspace"), "Unsupported channel"),
            (ContentRequest("reply", channel="X", screenshot=b"%PDF", screenshot_type="application/pdf"), "image"),
        ]
        for request, expected in cases:
            with self.subTest(expected=expected):
                self.assertIn(expected, request_problem(request))

    def test_valid_requests_have_no_problem(self) -> None:
        for request in (
            ContentRequest("reply", channel="X", original_content="why are bag fees so high?"),
            ContentRequest("reply", channel="Instagram", screenshot=PNG, screenshot_type="image/png"),
            ContentRequest("reply", channel="X", original_content="https://x.com/a/1", screenshot=PNG, screenshot_type="image/png"),
            ContentRequest("press_release", "new app goes live", "internal Slack"),
            ContentRequest("meme", "boarding", "Instagram"),
        ):
            with self.subTest(request=request.content_type + " " + request.channel):
                self.assertEqual(request_problem(request), "")


class ReplyInputTests(unittest.TestCase):
    def setUp(self) -> None:
        _clean_env(self)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.calls = []

        def generator(prompt: str, client: object = None, **kwargs: object) -> str:
            self.calls.append(dict(kwargs, prompt=prompt))
            return "come with your own plane next time"

        self.pipeline = ContentPipeline(KnowledgeBase.load(), self.directory.name, generator)

    def _draft(self, request: ContentRequest) -> str:
        return self.pipeline.draft(request, self.pipeline.monitor(request))

    def test_pasted_text_is_the_post_to_reply_to(self) -> None:
        self._draft(ContentRequest("reply", channel="X", original_content="Why are bag fees so high?"))
        prompt = self.calls[0]["prompt"]
        self.assertIn("POST TO REPLY TO:\nWhy are bag fees so high?", prompt)
        self.assertNotIn("Topic:", prompt)
        self.assertEqual(self.calls[0]["images"], ())

    def test_link_only_reply_is_refused_before_any_model_call(self) -> None:
        with self.assertRaisesRegex(PipelineError, "Links can't be opened"):
            self._draft(ContentRequest("reply", channel="X", original_content="https://x.com/a/status/1"))
        self.assertEqual(self.calls, [])

    def test_screenshot_is_attached_and_the_prompt_says_to_read_it(self) -> None:
        self._draft(ContentRequest("reply", channel="X", screenshot=PNG, screenshot_type="image/png"))
        call = self.calls[0]
        self.assertEqual(call["images"], (("image/png", PNG),))
        self.assertIn("attached screenshot", call["prompt"])
        self.assertIn(CANNOT_READ_SCREENSHOT, call["prompt"])
        self.assertNotIn("POST TO REPLY TO", call["prompt"])

    def test_link_with_screenshot_is_accepted_and_the_link_is_not_opened(self) -> None:
        self._draft(ContentRequest(
            "reply", channel="X", original_content="https://x.com/a/status/1", screenshot=PNG, screenshot_type="image/png",
        ))
        self.assertIn("Links are not opened", self.calls[0]["prompt"])
        self.assertIn("attached screenshot as well", self.calls[0]["prompt"])


class SelfLearningTests(unittest.TestCase):
    def setUp(self) -> None:
        _clean_env(self)
        self.knowledge_base = KnowledgeBase.load()
        self.request = ContentRequest("reply", channel="X", original_content="Why are bag fees so high?")

    def _pipeline(self, directory: str) -> ContentPipeline:
        return ContentPipeline(self.knowledge_base, directory, lambda _prompt, **_: "Short punchy draft\n\nHUMAN REVIEW NOTES\n- check")

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
            other_channel = ContentRequest("reply", channel="Instagram", original_content="Why are bag fees so high?")
            other_type = ContentRequest("meme", "summer sale", "X")
            self.assertIn("No learned feedback yet", pipeline.brief(other_channel, context))
            self.assertIn("No learned feedback yet", pipeline.brief(other_type, context))
            self.assertIn("Too formal for X.", pipeline.brief(self.request, context))

    def test_learned_feedback_is_separate_from_company_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = self._pipeline(directory)
            pipeline.record_decline(self.request, "UNIQUE-REASON-MARKER")
            prompt = pipeline.brief(self.request, pipeline.monitor(self.request))
            primary = prompt.split("PRIMARY CONTEXT")[1].split("SECONDARY CONTEXT")[0]
            secondary = prompt.split("SECONDARY CONTEXT")[1].split("GUARDRAILS")[0]
            learned = prompt.split("LEARNED FEEDBACK — ")[1]
            self.assertNotIn("UNIQUE-REASON-MARKER", primary + secondary)
            self.assertIn("UNIQUE-REASON-MARKER", learned)
            self.assertIn("NOT company facts", prompt)


class VoiceRulesFromKnowledgeBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        _clean_env(self)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.pipeline = ContentPipeline(KnowledgeBase.load(), self.directory.name)

    def _prompt(self, request: ContentRequest) -> str:
        return self.pipeline.brief(request, self.pipeline.monitor(request))

    def _voice(self, request: ContentRequest) -> str:
        prompt = self._prompt(request)
        return prompt[prompt.index("VOICE RULES — "):prompt.index("EXAMPLES — ")]

    def test_rules_depend_on_channel_and_type(self) -> None:
        x_reply = self._voice(ContentRequest("reply", channel="X", original_content="bag fees are a joke"))
        linkedin_post = self._voice(ContentRequest("post", "new routes", "LinkedIn"))
        slack_release = self._voice(ContentRequest("press_release", "new app", "internal Slack"))
        self.assertIn("One lowercase sentence, normally 3–12 words.", x_reply)
        self.assertNotIn("lowercase sentence", linkedin_post)
        self.assertIn("all-caps headline", linkedin_post)
        self.assertIn("internal announcement for colleagues", slack_release)
        self.assertNotIn("ENDS` line", linkedin_post)

    def test_specific_rules_come_before_general_ones(self) -> None:
        voice = self._voice(ContentRequest("reply", channel="X", original_content="bag fees are a joke"))
        order = [voice.index(marker) for marker in (
            "X, reply to post:", "Every reply to post:", "X in general:", "Brand voice everywhere:",
        )]
        self.assertEqual(order, sorted(order))

    def test_voice_and_examples_come_after_the_context(self) -> None:
        prompt = self._prompt(ContentRequest("meme", "boarding", "Instagram"))
        order = [prompt.index(marker) for marker in (
            "PRIMARY CONTEXT", "SECONDARY CONTEXT", "GUARDRAILS", "REQUEST", "VOICE RULES — ", "EXAMPLES — ",
            "LEARNED FEEDBACK — ", "FORMAT LIMITS",
        )]
        self.assertEqual(order, sorted(order))
        self.assertIn("POV: kids on a 3 AM flight", prompt[prompt.index("EXAMPLES — "):])

    def test_voice_documents_are_not_repeated_in_primary_context(self) -> None:
        prompt = self._prompt(ContentRequest("meme", "delays", "X"))
        primary = prompt.split("PRIMARY CONTEXT")[1].split("SECONDARY CONTEXT")[0]
        self.assertNotIn("(brand_voice.md)", primary)
        self.assertNotIn("(editorial_guardrails.md)", primary)
        self.assertIn("(company_profile.md)", primary)
        self.assertIn("(editorial_guardrails.md)", prompt.split("GUARDRAILS")[1].split("REQUEST")[0])

    def test_reviewer_only_sections_are_left_out(self) -> None:
        prompt = self._prompt(ContentRequest("post", "new routes", "LinkedIn"))
        for heading in ("### Sources and evidence", "### Review questions", "### Platform cues", "### Public context"):
            self.assertNotIn(heading, prompt)
        self.assertNotIn("restrained emoji use", prompt)

    def test_templates_hold_no_hardcoded_voice_rules(self) -> None:
        for path in Path("templates").glob("*.txt"):
            with self.subTest(template=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("emoji", text)
                self.assertFalse([line for line in text.splitlines() if line.startswith("- ")])
                if path.name != "system.txt":
                    self.assertEqual(text.count("{{voice_rules}}"), 1)
                    self.assertEqual(text.count("{{examples}}"), 1)


if __name__ == "__main__":
    unittest.main()
