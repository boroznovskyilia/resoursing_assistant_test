from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from check_docs import broken_links, local_targets


class DocumentationCheckerTests(unittest.TestCase):
    def test_external_links_anchors_and_fenced_examples_are_not_local_files(self):
        text = """[web](https://example.com) [section](#heading)
[email](mailto:hello@example.com)
```md
[example](not-a-real-file.md)
```
~~~md
[another example](also-not-a-file.md)
~~~
[actual](rules.md#behavior)
"""
        self.assertEqual(list(local_targets(text)), ["rules.md"])

    def test_missing_target_fails_and_creating_it_fixes_the_check(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs" / "rule.md").write_text(
                "[home](../README.md) [missing](details.md#behavior)", encoding="utf-8"
            )
            (root / "README.md").write_text("# Home", encoding="utf-8")
            self.assertEqual(broken_links(root), ["docs/rule.md: details.md"])
            (root / "docs" / "details.md").write_text("# Details", encoding="utf-8")
            self.assertEqual(broken_links(root), [])

    def test_generated_dependency_documents_are_ignored(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "node_modules").mkdir()
            (root / "node_modules" / "README.md").write_text(
                "[missing](missing.md)", encoding="utf-8"
            )
            self.assertEqual(broken_links(root), [])


if __name__ == "__main__":
    unittest.main()
