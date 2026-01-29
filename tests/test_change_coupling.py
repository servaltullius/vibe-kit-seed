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

    def test_parse_git_log_name_status_detects_rename_and_canonicalizes(self) -> None:
        text = "\n".join(
            [
                "__VIBE_COMMIT__cccccccccccccccccccccccccccccccccccccccc",
                "R100\ta/old.py\ta/new.py",
                "__VIBE_COMMIT__bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "M\ta/old.py",
                "",
            ]
        )
        commits = cc.parse_git_log_name_status(text, detect_renames=True, include_numstat=False)
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0].files, ["a/new.py"])
        self.assertEqual(commits[1].files, ["a/new.py"])

    def test_parse_git_log_name_status_parses_numstat_churn(self) -> None:
        text = "\n".join(
            [
                "__VIBE_COMMIT__cccccccccccccccccccccccccccccccccccccccc",
                "10\t5\tsrc/a.py",
                "M\tsrc/a.py",
                "__VIBE_COMMIT__bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "1\t1\tsrc/b.py",
                "M\tsrc/b.py",
                "",
            ]
        )
        commits = cc.parse_git_log_name_status(text, detect_renames=False, include_numstat=True)
        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0].churn, 15)
        self.assertEqual(commits[1].churn, 2)
        self.assertEqual(commits[0].numstat, [("src/a.py", 15)])
        self.assertEqual(commits[1].numstat, [("src/b.py", 2)])


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

        edges = cc.compute_edges(pair_counts=pair_counts, file_commit_counts=file_counts, min_pair_count=2)
        report = cc.build_report(
            edges=edges,
            file_commit_counts=file_counts,
            sum_couplings=sums,
            max_pairs=10,
        )
        pairs = report["pairs"]
        self.assertEqual(len(pairs), 2)
        self.assertTrue(any(p["a"] == "a" and p["b"] == "b" and p["count"] == 2 for p in pairs))
        self.assertTrue(any(p["a"] == "b" and p["b"] == "c" and p["count"] == 2 for p in pairs))
        self.assertTrue(all(abs(p["jaccard"] - 0.6667) < 1e-4 for p in pairs))


class TestChangeCouplingSuggestions(unittest.TestCase):
    def test_clusters_leaks_and_hubs(self) -> None:
        commits = [
            ["p1", "p2"],
            ["p1", "p2"],
            ["p1", "p2"],
            ["p3", "p4"],
            ["p3", "p4"],
            ["p3", "p4"],
            ["p2", "p3"],
            ["p2", "p3"],
        ]
        pair_counts, file_counts, sums, skipped = cc.compute_change_coupling(commits, max_files_per_commit=100)
        self.assertEqual(skipped, 0)

        edges = cc.compute_edges(pair_counts=pair_counts, file_commit_counts=file_counts, min_pair_count=2)
        strong_edges = [e for e in edges if e.jaccard >= 0.6]
        weak_edges = [e for e in edges if e.jaccard < 0.6]

        clusters, node_to_cluster = cc.compute_clusters(strong_edges, min_cluster_size=2, max_clusters=10)
        self.assertEqual(len(clusters), 2)
        self.assertTrue(any(c.get("nodes") == ["p1", "p2"] for c in clusters))
        self.assertTrue(any(c.get("nodes") == ["p3", "p4"] for c in clusters))
        self.assertEqual(node_to_cluster.get("p2"), 1)
        self.assertEqual(node_to_cluster.get("p3"), 2)

        leaks = cc.compute_boundary_leaks(weak_edges, node_to_cluster=node_to_cluster, max_boundary_leaks=10)
        self.assertEqual(len(leaks), 1)
        self.assertEqual(leaks[0]["a"], "p2")
        self.assertEqual(leaks[0]["b"], "p3")
        self.assertIn("playbooks", leaks[0])
        self.assertIsInstance(leaks[0]["playbooks"], list)
        self.assertGreaterEqual(len(leaks[0]["playbooks"]), 1)
        self.assertTrue(all("title" in pb for pb in leaks[0]["playbooks"]))

        hubs = cc.compute_hubs(
            weak_edges,
            file_commit_counts=file_counts,
            sum_couplings=sums,
            node_to_cluster=node_to_cluster,
            max_hubs=10,
        )
        self.assertTrue(any(h["node"] == "p2" for h in hubs))
        self.assertTrue(any(h["node"] == "p3" for h in hubs))


if __name__ == "__main__":
    unittest.main()
