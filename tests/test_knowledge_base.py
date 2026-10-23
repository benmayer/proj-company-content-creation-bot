"""Verification tests for knowledge-base selection against the real KB."""

import unittest

from src.knowledge_base import KnowledgeBase, PRIMARY, SECONDARY

CASES = [
    ("new route announcement for winter fares", "linkedin", "promotion_pattern", None),
    ("how we respond to easyJet and Wizz Air competitors", "x", None, "competitor_analysis"),
    ("passenger complaints about baggage fees and luggage", "instagram", None, "customer_feedback"),
]


class KnowledgeBaseSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.kb = KnowledgeBase.load()

    def test_representative_requests(self) -> None:
        for topic, channel, primary_type, secondary_type in CASES:
            with self.subTest(topic=topic):
                ctx = self.kb.select(topic, channel)
                primary_types = {i.document.metadata["type"] for i in ctx.primary}
                secondary_types = {i.document.metadata["type"] for i in ctx.secondary}
                self.assertTrue({"brand_voice", "company_profile"} <= primary_types)
                self.assertTrue(ctx.secondary)
                if primary_type:
                    self.assertIn(primary_type, primary_types)
                if secondary_type:
                    self.assertIn(secondary_type, secondary_types)

    def test_kinds_are_labelled_and_not_mixed(self) -> None:
        ctx = self.kb.select("market trends and competitors", "x")
        self.assertTrue(all(i.source_kind == PRIMARY and "primary" in i.document.source_path.parts for i in ctx.primary))
        self.assertTrue(all(i.source_kind == SECONDARY and "secondary" in i.document.source_path.parts for i in ctx.secondary))
        self.assertNotIn("source_register", {i.document.metadata["type"] for i in ctx.secondary})
        rendered = ctx.render()
        self.assertLess(rendered.index("PRIMARY:"), rendered.index("SECONDARY:"))

    def test_unmatched_topic_still_returns_nonempty_context(self) -> None:
        ctx = self.kb.select("zzzz qqqq")
        self.assertTrue(ctx.primary)
        self.assertTrue(ctx.secondary)

    def test_selection_is_deterministic(self) -> None:
        a = self.kb.select("baggage fees", "x")
        b = self.kb.select("baggage fees", "x")
        self.assertEqual(a.render(), b.render())

    def test_channel_and_content_type_widen_matching_context(self) -> None:
        press_release = self.kb.select("summer travel", "LinkedIn", "press_release")
        reply = self.kb.select("summer travel", "X", "reply")
        self.assertIn("promotion_pattern", {i.document.metadata["type"] for i in press_release.primary})
        self.assertIn("competitor_analysis", {i.document.metadata["type"] for i in reply.secondary})

    def test_every_channel_and_content_type_has_a_profile_document(self) -> None:
        from src.channel_profiles import (
            CHANNELS, CONTENT_TYPES, channel_content_types, channel_type_rules, content_type_rules, get_channel_profile,
        )
        from src.prompt_templates import available_content_types

        for channel in CHANNELS:
            profile = get_channel_profile(channel)
            self.assertTrue(profile.tone and profile.format)
            self.assertTrue(profile.source.startswith("knowledge_base/primary/channel_"))
            for content_type in channel_content_types(channel):
                self.assertTrue(channel_type_rules(channel, content_type), f"{channel} {content_type}")
        for content_type in CONTENT_TYPES:
            self.assertTrue(content_type_rules(content_type))
        self.assertEqual(set(CONTENT_TYPES), set(available_content_types()))

    def test_channels_offer_the_agreed_content_types(self) -> None:
        from src.channel_profiles import CHANNELS, channel_content_types, content_type_label

        self.assertEqual(
            {channel: channel_content_types(channel) for channel in CHANNELS},
            {
                "LinkedIn": ("post", "press_release"),
                "Instagram": ("post", "reply", "meme"),
                "X": ("post", "reply", "meme"),
                "internal Slack": ("press_release", "post", "meme"),
            },
        )
        self.assertEqual(content_type_label("press_release", "internal Slack"), "press release (internal)")
        self.assertEqual(content_type_label("press_release", "LinkedIn"), "press release")
        self.assertEqual(content_type_label("post"), "regular post")
        self.assertEqual(content_type_label("reply"), "reply to post")

    def test_profile_edits_apply_without_a_restart(self) -> None:
        import shutil
        import tempfile
        from pathlib import Path

        from src.channel_profiles import get_channel_profile
        from src.knowledge_base import DEFAULT_ROOT

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "primary").mkdir()
            shutil.copy(DEFAULT_ROOT / "primary" / "channel_x.md", root / "primary" / "channel_x.md")
            self.assertIn("deadpan", get_channel_profile("X", root).tone)
            path = root / "primary" / "channel_x.md"
            path.write_text(path.read_text(encoding="utf-8").replace("deadpan", "EDITED"), encoding="utf-8")
            self.assertIn("EDITED", get_channel_profile("X", root).tone)

    def test_profile_documents_are_never_selected_as_topic_context(self) -> None:
        ctx = self.kb.select("meme channel profile voice rules examples instagram x", "X", "meme")
        types = {i.document.metadata["type"] for i in ctx.primary}
        self.assertFalse(types & {"channel_profile", "content_type_profile", "channel_examples"})

    def test_mentioning_ryanair_does_not_pull_in_every_document(self) -> None:
        ctx = self.kb.select("ryanair delayed my flight again", "X", "reply")
        self.assertEqual(
            {i.document.metadata["type"] for i in ctx.primary},
            {"brand_voice", "company_profile", "editorial_guardrails"},
        )


if __name__ == "__main__":
    unittest.main()
