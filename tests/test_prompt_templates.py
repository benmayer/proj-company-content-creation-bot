"""Verification tests for reusable prompt templates."""

from pathlib import Path
import tempfile
import unittest

from src.prompt_templates import (
    NO_EXAMPLES,
    PromptTemplateError,
    available_content_types,
    render_prompt,
    render_template,
)


class PromptTemplateTests(unittest.TestCase):
    def test_supported_templates_render_complete_prompts(self) -> None:
        self.assertEqual(available_content_types(), ("meme", "post", "press_release", "reply"))
        for content_type in available_content_types():
            prompt = render_prompt(
                content_type,
                request="Promote a summer travel idea.",
                primary_context="Approved company facts.",
                secondary_context="Industry context only.",
                voice_rules="Use clear, playful language.",
                format_limits="150 words maximum.",
                channel="X" if content_type != "press_release" else "LinkedIn",
            ).text
            self.assertNotIn("{{", prompt)
            self.assertIn("Approved company facts.", prompt)
            self.assertIn("Industry context only.", prompt)
            self.assertNotIn("human review notes", prompt.lower())

    def test_all_channel_and_content_type_combinations_render(self) -> None:
        from src.channel_profiles import CHANNELS, channel_content_types, channel_type_rules

        for channel in CHANNELS:
            for content_type in channel_content_types(channel):
                with self.subTest(channel=channel, content_type=content_type):
                    prompt = render_prompt(
                        content_type,
                        request="Announce a sourced route update.",
                        primary_context="Company facts.",
                        secondary_context="Industry context.",
                        voice_rules="Approved voice.",
                        format_limits="Keep it concise.",
                        channel=channel,
                    )
                    self.assertNotIn("{{", prompt.text)
                    self.assertIn(channel, prompt.user)
                    self.assertIn(channel_type_rules(channel, content_type).splitlines()[0], prompt.user)
                    self.assertNotIn("Approved voice.", prompt.system)

    def test_examples_are_plain_text_or_a_placeholder(self) -> None:
        def examples(channel: str, content_type: str) -> str:
            user = render_prompt(content_type, "r", "p", "s", "v", "f", channel=channel).user
            return user.split("EXAMPLES — ")[1].split("LEARNED FEEDBACK — ")[0]

        self.assertIn("come with your own plane next time", examples("X", "reply"))
        self.assertIn("POV: kids on a 3 AM flight", examples("Instagram", "meme"))
        self.assertIn(NO_EXAMPLES, examples("internal Slack", "post"))
        self.assertNotIn("https://", examples("X", "reply"))

    def test_adding_one_template_file_supports_a_new_content_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "system.txt").write_text("System fact-only rule.", encoding="utf-8")
            (root / "announcement.txt").write_text(
                "Request: {{request}}\nPrimary: {{primary_context}}\n"
                "Secondary: {{secondary_context}}\nVoice: {{voice_rules}}\n"
                "Limits: {{format_limits}}",
                encoding="utf-8",
            )

            prompt = render_template(
                "announcement",
                {
                    "request": "Write an announcement.",
                    "primary_context": "Company fact.",
                    "secondary_context": "Market note.",
                    "voice_rules": "Be direct.",
                    "format_limits": "80 words.",
                },
                templates_dir=root,
            )
            self.assertIn("Write an announcement.", prompt)
            self.assertNotIn("{{", prompt)

    def test_missing_values_and_unknown_types_fail_actionably(self) -> None:
        with self.assertRaisesRegex(PromptTemplateError, "not found"):
            render_prompt("missing", "request", "primary", "secondary", "voice", "limits")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "system.txt").write_text("System", encoding="utf-8")
            (root / "broken.txt").write_text("{{request}} {{missing}}", encoding="utf-8")
            with self.assertRaisesRegex(PromptTemplateError, "missing values"):
                render_template("broken", {"request": "A request"}, templates_dir=root)


class LearnedFeedbackTemplateTests(unittest.TestCase):
    def test_every_template_renders_learned_feedback(self) -> None:
        for content_type in available_content_types():
            with self.subTest(content_type=content_type):
                prompt = render_prompt(
                    content_type, "request", "primary", "secondary", "voice", "limits",
                    channel="internal Slack" if content_type != "reply" else "X",
                    learned_feedback="LEARNED-MARKER",
                )
                self.assertIn("LEARNED-MARKER", prompt.user)


if __name__ == "__main__":
    unittest.main()
