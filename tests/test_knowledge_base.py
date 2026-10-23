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


if __name__ == "__main__":
    unittest.main()
