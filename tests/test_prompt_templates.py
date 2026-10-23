"""Verification tests for reusable prompt templates."""

from pathlib import Path
import tempfile
import unittest

from src.prompt_templates import (
    PromptTemplateError,
    available_content_types,
    render_prompt,
    render_template,
)


class PromptTemplateTests(unittest.TestCase):
    def test_supported_templates_render_complete_prompts(self) -> None:
        self.assertEqual(
            available_content_types(),
            ("campaign_brief", "meme", "post_update", "press_release", "reply", "social_post"),
        )
        for content_type in available_content_types():
            prompt = render_prompt(
                content_type,
                request="Promote a summer travel idea.",
                primary_context="Approved company facts.",
                secondary_context="Industry context only.",
                voice_rules="Use clear, playful language.",
                format_limits="150 words maximum.",
            )
            self.assertNotIn("{{", prompt)
            self.assertIn("Approved company facts.", prompt)
            self.assertIn("Industry context only.", prompt)
            self.assertIn("human review", prompt.lower())

    def test_all_channel_and_content_type_combinations_render(self) -> None:
        from src.channel_profiles import CHANNELS, CONTENT_TYPES

        for channel in CHANNELS:
            for content_type in CONTENT_TYPES:
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
                    self.assertNotIn("{{", prompt)
                    self.assertIn(channel, prompt)
                    self.assertIn(content_type.replace("_", " "), prompt)

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


if __name__ == "__main__":
    unittest.main()
