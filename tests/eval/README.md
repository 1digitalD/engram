# Golden capture eval (SQ-03)

A hand-labeled fixture set that scores capture extraction quality end to end:
`/api/v4/capture` → `extract_capture_candidates` → `reconcile_candidates` →
applied changes / suggestions. It exists because every prompt/model change to
the capture pipeline so far shipped without a fixed measure of extraction
quality — regressions were discovered only when the user deleted the noisy
entities it created.

**This is a decision tool, not a CI gate.** It calls the live OpenAI API, so
it costs money and its output is not perfectly reproducible run to run. It is
skipped by default and must never run automatically in CI.

## Cost warning

Running this suite makes one real OpenAI call per fixture (extraction) plus
additional calls for reconciliation and decision-extraction on any fixture
that produces entity/link candidates. With ~20 fixtures this is a small
number of requests, but it is **not free** and **not offline** — don't wire
it into a pre-commit hook or a CI pipeline.

## How to run

```bash
ENGRAM_ALLOW_TEST_AI=1 \
TEST_DATABASE_URL=postgresql://engram:engram@localhost:5433/engram_test \
OPENAI_API_KEY=sk-... \
./venv/bin/pytest tests/eval -q -s
```

- `ENGRAM_ALLOW_TEST_AI=1` is required — without it every test in this
  directory is skipped at collection, before any database fixture runs (see
  `pytestmark = pytest.mark.skipif(...)` at the top of
  `test_capture_golden.py`). This mirrors the existing gate used by
  `services/v4_extraction.py`, `services/v4_decisions.py`, etc. to keep the
  normal test suite fast, deterministic, and offline.
- `-s` is required to see the printed precision/recall table — pytest
  captures stdout by default.
- `OPENAI_API_KEY` must be a real key. Without it, individual fixtures skip
  with `OPENAI_API_KEY not set`.
- Run a single fixture with `-k`, e.g. `pytest tests/eval -q -s -k close_task_after_sessions`.

Without `ENGRAM_ALLOW_TEST_AI=1`, running `pytest tests/eval -q` (no `-s`
needed) must show all fixtures skipped and must not touch any database —
this is what CI/normal `pytest` runs will do.

## What it checks

Each fixture describes one capture and an `expected` block:

- `must_create` / `target_status(_options)` / `follow_up_expected` — **recall**
  checks: what a good pipeline *should* propose or apply. Real model output
  varies run to run, so a miss here is reported in the table and rolled into
  the aggregate recall score, but does **not** fail the test by itself.
- `forbid_create` / `forbid_decision` / `expect_no_entities` — **precision**
  checks: outcomes that must never happen (duplicate entities, discussion
  fragments turned into tasks, spurious decisions, noise on junk input). Any
  match here **fails the test** — these are the regressions that matter.

Output looks like:

```
=== Golden capture eval — SQ-03 ===
fixture                               recall        precision    creates  notes
close_task_after_sessions             recall=0/0    precision=ok creates=0  status:ok(done)
pending_policies_followup             recall=0/0    precision=ok creates=0  follow_up:ok
meeting_transcript_action_items       recall=4/6    precision=ok creates=5
...

=== Aggregate ===
fixtures run: 20
recall: 34/41 required entities present (83%)
precision: 18/20 fixtures with zero forbidden outcomes
total forbidden-outcome violations: 2
```

## Adding a fixture

Edit `tests/eval/fixtures.py` and append a dict to `FIXTURES`:

```python
{
    "id": "unique_snake_case_id",
    "kind": "status_update",  # meeting_notes | status_update | delegation | junk | reference | direction
    "content": "the exact capture text",
    "attached_thread": {          # optional — omit for an unattached capture
        "type": "task",
        "title": "Existing thing to seed",
        "status": "in_progress",  # optional
        "attach_as_thread": True, # False = seed only, don't pass thread_id
                                   # (use this for "should merge, not duplicate" cases)
    },
    "expected": {
        "must_create": [{"type": "task", "title_contains": "..."}],
        "forbid_create": [{"type": "task", "title_contains": "..."}],
        "forbid_decision": False,
        "expect_no_entities": False,
        "target_status": "done",           # or target_status_options: [...]
        "follow_up_expected": False,
    },
    "notes": "why this fixture exists / what real failure it's based on",
},
```

Prefer real (anonymized) capture text over invented examples — the fixtures
that catch regressions are the ones drawn from actual production failures.
`title_contains` is a case-insensitive substring match against the proposed
or created entity's title (or a decision's `statement`), so keep it short
and distinctive rather than matching the whole title verbatim.

Scoring logic lives in `tests/eval/fixtures.py::score_fixture` and
`collect_proposed_creates` — both are pure functions with no DB/network
dependency, so fixture changes can be sanity-checked without running the
suite:

```bash
PYTHONPATH=tests/eval ./venv/bin/python -c "
from fixtures import FIXTURES
print(len(FIXTURES), 'fixtures')
"
```
