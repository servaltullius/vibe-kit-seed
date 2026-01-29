import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".vibe" / "brain"))

import change_coupling as cc  # noqa: E402


class TestChangeCouplingParse(unittest.TestCase):
    def test_parse_git_log_name_only(self) -> None:
        text = "\n".join(
            [
                "__VIBE_COMMIT__aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "a.txt",
                "b.txt",
                "",
                "__VIBE_COMMIT__bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "b.txt",
                "c.txt",
                "",
            ]
        )
        commits = cc.parse_git_log_name_only(text)
        self.assertEqual(commits, [["a.txt", "b.txt"], ["b.txt", "c.txt"]])


class TestChangeCouplingCompute(unittest.TestCase):
    def test_compute_change_coupling_pairs_and_jaccard(self) -> None:
        commits = [["a", "b", "c"], ["b", "c"], ["a", "b"]]
        pair_counts, file_counts, sums, skipped = cc.compute_change_coupling(commits, max_files_per_commit=100)
        self.assertEqual(skipped, 0)
        self.assertEqual(pair_counts.get(("a", "b")), 2)
        self.assertEqual(pair_counts.get(("a", "c")), 1)
        self.assertEqual(pair_counts.get(("b", "c")), 2)
        self.assertEqual(file_counts, {"a": 2, "b": 3, "c": 2})
        self.assertEqual(sums, {"a": 3, "b": 4, "c": 3})

        report = cc.build_report(
            pair_counts=pair_counts,
            file_commit_counts=file_counts,
            sum_couplings=sums,
            min_pair_count=2,
            max_pairs=10,
        )
        pairs = report["pairs"]
        self.assertEqual(len(pairs), 2)
        self.assertTrue(any(p["a"] == "a" and p["b"] == "b" and p["count"] == 2 for p in pairs))
        self.assertTrue(any(p["a"] == "b" and p["b"] == "c" and p["count"] == 2 for p in pairs))
        self.assertTrue(all(abs(p["jaccard"] - 0.6667) < 1e-4 for p in pairs))


if __name__ == "__main__":
    unittest.main()

