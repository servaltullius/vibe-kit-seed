# vibe-kit Coupling Suggestions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend `vibe coupling` to generate actionable decoupling/refactoring suggestions: clusters (module candidates), boundary leaks, and hubs.

**Architecture:** Build a thresholded co-change graph from `pair_counts` + file commit counts (count + Jaccard). Compute connected-components as clusters. Then compute cross-cluster edges as “boundary leaks” and rank nodes that connect many clusters as “hubs”. Emit all results into `.vibe/reports/change_coupling.json` with small, stable summaries (bounded list sizes).

**Tech Stack:** Python 3 (stdlib only), existing `change_coupling.py`.

---

### Task 1: Add config knobs and CLI flags

**Files:**
- Modify: `scripts/vibe.py`
- Modify: `.vibe/brain/change_coupling.py`

**Step 1: Add flags**
- Add `--min-jaccard` (default conservative, e.g. 0.2).
- Add `--min-cluster-size`, `--max-clusters`, `--max-boundary-leaks`, `--max-hubs`.

**Step 2: Verify parsing**
- Run: `python3 scripts/vibe.py coupling --help`
- Expected: new flags show up.

---

### Task 2: Implement clustering + suggestions

**Files:**
- Modify: `.vibe/brain/change_coupling.py`

**Step 1: Build thresholded edge list**
- From all `pair_counts`, compute edges that meet `min_pair_count` AND `min_jaccard`.

**Step 2: Compute connected components**
- Build adjacency and compute components (DFS/BFS).
- Keep clusters with size >= `min_cluster_size`.
- For each cluster: include nodes, internal edge count, internal count-sum, avg Jaccard, and top internal edges.

**Step 3: Compute boundary leaks**
- From thresholded edges, keep cross-cluster edges.
- Rank by `count` then `jaccard`, emit top N.

**Step 4: Compute hubs**
- For each node, compute:
  - `sum_couplings` (already computed)
  - `connected_clusters_count`
  - `cross_edge_count_sum`
- Emit top N hubs with justification fields.

**Step 5: Write report**
- Add top-level keys: `clusters`, `boundary_leaks`, `hubs` in JSON.

---

### Task 3: Surface minimal summary in LATEST_CONTEXT

**Files:**
- Modify: `.vibe/brain/summarizer.py`

**Step 1: Add summary lines**
- Show top 1 cluster and top 1 boundary leak (if present), keeping output short.

---

### Task 4: Tests

**Files:**
- Modify: `tests/test_change_coupling.py`

**Step 1: Add failing test for clusters/leaks/hubs**
- Create a tiny synthetic commit history with two clusters and one cross edge.
- Assert cluster sizes and that a known node appears as a hub.

**Step 2: Run tests**
- Run: `python3 -m unittest discover -s tests -p 'test*.py' -v`
- Expected: PASS.

---

### Task 5: Verify + ship

**Step 1: Smoke-run**
- Run: `python3 scripts/vibe.py coupling --group-by dir --dir-depth 2 --top 5`
- Expected: prints clusters/leaks/hubs summary and writes report.

**Step 2: Commit + push**
- Commit with message like `feat: add coupling-based decoupling suggestions`.
- Push to `origin/main`.

