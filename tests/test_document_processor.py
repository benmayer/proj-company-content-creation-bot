"""Verification tests for the Markdown document processor."""

from pathlib import Path
import tempfile
import unittest

from src.document_processor import ingest_directory, ingest_document


class DocumentProcessorTests(unittest.TestCase):
    def test_ingests_directory_and_preserves_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "first.md").write_text(
                "---\n"
                "type: company_profile\n"
                "title: Example\n"
                "tags: [demo]\n"
                "---\n"
                "# Overview\n"
                "This is the document overview.\n"
                "\n"
                "## Details\n"
                "These details are retained.\n",
                encoding="utf-8",
            )
            (root / "nested").mkdir()
            (root / "nested" / "second.md").write_text(
                "---\n"
                "type: market_trend\n"
                "description: A market note\n"
                "---\n"
                "## Trend\n"
                "A non-empty market section.\n",
                encoding="utf-8",
            )

            documents = ingest_directory(root)

            self.assertEqual([document.source_path.name for document in documents], ["first.md", "second.md"])
            sections = [section for document in documents for section in document.sections]
            self.assertEqual([section.heading for section in sections], ["Overview", "Details", "Trend"])
            self.assertTrue(all(section.body for section in sections))
            self.assertEqual(documents[0].metadata["tags"], ["demo"])
            self.assertIs(sections[0].metadata, documents[0].metadata)
            self.assertEqual(sections[0].source_path, root / "first.md")

    def test_ignores_headings_inside_fenced_code_and_rejects_invalid_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            document_path = root / "document.md"
            document_path.write_text(
                "---\n"
                "type: example\n"
                "---\n"
                "## Real heading\n"
                "Body.\n"
                "```markdown\n"
                "## Not a heading\n"
                "```\n",
                encoding="utf-8",
            )
            document = ingest_document(document_path)
            self.assertEqual([section.heading for section in document.sections], ["Real heading"])

            invalid_path = root / "invalid.md"
            invalid_path.write_text("# Missing frontmatter\n\nBody", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frontmatter"):
                ingest_document(invalid_path)


if __name__ == "__main__":
    unittest.main()
