"""Golden-set fixtures for the capture extraction quality eval (SQ-03).

Each fixture describes one `/api/v4/capture` call and what a *good* pipeline
should (and should not) do with it. Several are drawn near-verbatim from real
production failures logged in
`docs/iterations/ITERATION_19_SIGNAL_QUALITY_PLAN.md`.

Fixture shape
-------------
    {
        "id": str,                     # unique, used as the pytest id
        "kind": str,                   # one of KINDS
        "content": str,                # the capture text
        "attached_thread": {           # optional — seeds a pre-existing entity
            "type": "task" | "project" | "person" | ...,
            "title": str,
            "status": str,             # optional, defaults to the type's default
            "content": str,            # optional
            "attach_as_thread": bool,  # default True — pass its id as
                                        # capture's `thread_id` (capture-sheet
                                        # attachment). False just seeds the
                                        # entity in the DB so reconciliation
                                        # can find/dedup it without an
                                        # explicit attachment (the "should
                                        # merge, not duplicate" case).
        },
        "expected": {
            "must_create": [{"type": ..., "title_contains": ...}, ...],
            "forbid_create": [{"type": ..., "title_contains": ...}, ...],
            "forbid_decision": bool,       # no create_decision suggestion at all
            "expect_no_entities": bool,    # nothing beyond the source note
            "target_status": str,          # single acceptable status
            "target_status_options": [str],# any-of acceptable statuses
            "follow_up_expected": bool,    # a follow_up_at should get set
        },
        "notes": str,                  # human-readable rationale, not asserted
    }

Only `forbid_*` / `expect_no_entities` are hard-asserted by the test module
(a forbidden outcome is a precision regression). `must_create`,
`target_status*`, and `follow_up_expected` are scored as recall and printed,
but do not fail the test on their own — see tests/eval/README.md for why.
"""

KINDS = {"meeting_notes", "status_update", "delegation", "junk", "reference", "direction"}


FIXTURES = [
    # ── Real production failures (near-verbatim) ──────────────────────────
    {
        "id": "close_task_after_sessions",
        "kind": "status_update",
        "content": (
            "Had 3 successful sessions on this week over week. Next ones happening "
            "tomorrow. This has been a success. We can close this task now."
        ),
        "attached_thread": {
            "type": "task",
            "title": "Coaching pilot with new hires",
            "status": "in_progress",
        },
        "expected": {
            "target_status": "done",
            "forbid_create": [{"type": "task", "title_contains": "Close"}],
            "forbid_decision": True,
        },
        "notes": (
            "Real failure: model proposed create_task 'Close task' (dismissed) and "
            "recorded a spurious decision instead of closing the attached task."
        ),
    },
    {
        "id": "pending_policies_followup",
        "kind": "status_update",
        "content": (
            "This is pending until next week since this week we had a few off days "
            "and no decision has been made on the policies yet."
        ),
        "attached_thread": {
            "type": "task",
            "title": "Finalize expense policy rewrite",
            "status": "in_progress",
        },
        "expected": {
            "follow_up_expected": True,
            "target_status_options": ["waiting", "in_progress"],
            "forbid_create": [{"type": "task", "title_contains": "Decide on policies"}],
        },
        "notes": (
            "Real failure: model proposed create_task 'Decide on policies' instead "
            "of setting follow_up_at + waiting status on the attached task."
        ),
    },

    # ── Status updates ─────────────────────────────────────────────────────
    {
        "id": "status_update_deictic_shipped",
        "kind": "status_update",
        "content": "Shipped it. This one's done, closing it out.",
        "attached_thread": {
            "type": "task",
            "title": "Ship parser fix for telemetry pipeline",
            "status": "in_progress",
        },
        "expected": {
            "target_status": "done",
            "forbid_create": [
                {"type": "task", "title_contains": "Shipped it"},
                {"type": "task", "title_contains": "closing it out"},
            ],
        },
        "notes": "Deictic 'it'/'this one' reference to the attached task — no new task noise expected.",
    },
    {
        "id": "status_update_blocked_legal",
        "kind": "status_update",
        "content": "This is now blocked on legal sign-off before we can move forward.",
        "attached_thread": {
            "type": "task",
            "title": "Vendor security review",
            "status": "in_progress",
        },
        "expected": {
            "target_status": "blocked",
        },
        "notes": "Status should flip to blocked on the attached task, not spawn a separate 'get legal sign-off' task.",
    },
    {
        "id": "status_update_no_duplicate_project",
        "kind": "status_update",
        "content": (
            "Quick update on Memory Lookup Rollout — infra is provisioned, waiting "
            "on the data migration script."
        ),
        "attached_thread": {
            "type": "project",
            "title": "Memory Lookup Rollout",
            "status": "active",
            "attach_as_thread": False,
        },
        "expected": {
            "forbid_create": [{"type": "project", "title_contains": "Memory Lookup"}],
        },
        "notes": (
            "Project is seeded but not explicitly attached — extraction/reconciliation "
            "should recognize it by name and link/update, not mint a duplicate."
        ),
    },
    {
        "id": "status_update_dedup_merge_person",
        "kind": "status_update",
        "content": "Priya flagged that the rollout doc still needs a review pass before Friday.",
        "attached_thread": {
            "type": "person",
            "title": "Priya Dhandapani",
            "attach_as_thread": False,
        },
        "expected": {
            "forbid_create": [{"type": "person", "title_contains": "Priya"}],
        },
        "notes": (
            "First-name-only mention of an existing person should link to "
            "'Priya Dhandapani', not create a second 'Priya' entity (SQ-08 person hygiene)."
        ),
    },
    {
        "id": "status_update_followup_two_weeks",
        "kind": "status_update",
        "content": "Let's revisit this in two weeks once the vendor gets back to us.",
        "attached_thread": {
            "type": "task",
            "title": "Vendor contract renewal terms",
            "status": "waiting",
        },
        "expected": {
            "follow_up_expected": True,
            "forbid_create": [{"type": "task", "title_contains": "revisit"}],
        },
        "notes": "Explicit re-check date should set follow_up_at on the attached task, not spawn a 'revisit' task.",
    },

    # ── Meeting notes ───────────────────────────────────────────────────────
    {
        "id": "meeting_transcript_action_items",
        "kind": "meeting_notes",
        "content": (
            "Weekly platform sync — notes\n\n"
            "Discussion:\n"
            "- Endorse L2 priority for the Q3 roadmap.\n"
            "- Treat L3 as deliberate defer, not a cut.\n"
            "- Name L3 defer explicitly on slide 5 so exec doesn't assume it's dropped.\n"
            "- Attend all hands in Vancouver this quarter.\n\n"
            "Action Items:\n"
            "- Akash to ship the L2 rollout plan doc by Friday.\n"
            "- Priya to follow up with legal on the vendor contract by next Tuesday.\n"
            "- Sam to schedule the customer migration call with the Acme team.\n"
        ),
        "expected": {
            "must_create": [
                {"type": "task", "title_contains": "rollout plan"},
                {"type": "task", "title_contains": "legal"},
                {"type": "task", "title_contains": "migration call"},
                {"type": "person", "title_contains": "Akash"},
                {"type": "person", "title_contains": "Priya"},
                {"type": "person", "title_contains": "Sam"},
            ],
            "forbid_create": [
                {"type": "task", "title_contains": "Endorse"},
                {"type": "task", "title_contains": "Treat L3"},
                {"type": "task", "title_contains": "Name L3"},
                {"type": "task", "title_contains": "all hands"},
                {"type": "task", "title_contains": "Attend"},
            ],
        },
        "notes": (
            "Real failure pattern: discussion fragments ('Endorse L2 priority', "
            "'Name L3 defer on slide 5') and meeting logistics ('Attend all hands') "
            "get proposed as tasks alongside the 3 real action items (SQ-07)."
        ),
    },
    {
        "id": "meeting_notes_standup_decision",
        "kind": "meeting_notes",
        "content": (
            "Standup: decided to launch the beta on 2026-07-15. Sam will send the "
            "launch checklist to the team by Friday."
        ),
        "expected": {
            "must_create": [
                {"type": "task", "title_contains": "launch checklist"},
                {"type": "person", "title_contains": "Sam"},
            ],
        },
        "notes": "An explicit commitment ('decided to launch...') plus one real action item.",
    },
    {
        "id": "meeting_notes_logistics_only",
        "kind": "meeting_notes",
        "content": (
            "All-hands is in Austin the week of the 14th. Most of the team is "
            "attending; please block your calendars, no prep needed."
        ),
        "expected": {
            "expect_no_entities": True,
        },
        "notes": "Pure logistics FYI — nothing actionable, no task/project/person should be created.",
    },

    # ── Delegation ───────────────────────────────────────────────────────────
    {
        "id": "delegation_priya_rollout_comms",
        "kind": "delegation",
        "content": "Asked Priya to own the rollout comms, check in with her Friday.",
        "expected": {
            "must_create": [{"type": "task", "title_contains": "rollout comms"}],
            "forbid_create": [{"type": "project", "title_contains": "rollout"}],
        },
        "notes": "Delegation with a named owner and an implicit check-in date — should stay a single task, not spin up a project.",
    },
    {
        "id": "delegation_sam_vendor_contract",
        "kind": "delegation",
        "content": "Please have Sam take point on the vendor contract renewal — flag me if he needs anything.",
        "expected": {
            "must_create": [{"type": "task", "title_contains": "vendor contract"}],
            "forbid_create": [{"type": "project", "title_contains": "vendor"}],
        },
        "notes": "Simple delegation, no attached thread — should resolve to one task assigned to Sam.",
    },

    # ── Junk ────────────────────────────────────────────────────────────────
    {
        "id": "junk_test",
        "kind": "junk",
        "content": "test",
        "expected": {"expect_no_entities": True},
        "notes": "Literal test input — must not produce any entities or suggestions.",
    },
    {
        "id": "junk_test_slice_verification",
        "kind": "junk",
        "content": "test slice verification",
        "expected": {"expect_no_entities": True},
        "notes": "Developer test capture used to smoke-test the slice pipeline itself.",
    },
    {
        "id": "junk_random_chars",
        "kind": "junk",
        "content": "asdf asdf",
        "expected": {"expect_no_entities": True},
        "notes": "Keyboard noise — must not be mistaken for content worth extracting.",
    },

    # ── Reference ───────────────────────────────────────────────────────────
    {
        "id": "reference_url_share",
        "kind": "reference",
        "content": (
            "Sharing the design doc for the new onboarding flow, take a look before "
            "Thursday: https://docs.example.com/onboarding-design"
        ),
        "expected": {
            "must_create": [{"type": "resource", "title_contains": "onboarding"}],
            "forbid_create": [{"type": "task", "title_contains": "onboarding"}],
        },
        "notes": "A URL share with a line of context should become a resource, not a task ('take a look' is not an action item).",
    },
    {
        "id": "reference_doc_link_bare",
        "kind": "reference",
        "content": "https://github.com/acme/agent-platform/pull/482 — the PR for the parser fix.",
        "expected": {
            "forbid_create": [
                {"type": "task", "title_contains": "parser"},
                {"type": "project", "title_contains": "parser"},
            ],
        },
        "notes": "A bare link share — resource creation is a reasonable outcome, task/project creation is not.",
    },
    {
        "id": "reference_logistics_all_hands",
        "kind": "reference",
        "content": "FYI — the Q3 all-hands dates moved to August 3-5 in Vancouver.",
        "expected": {
            "expect_no_entities": True,
        },
        "notes": "Pure FYI logistics note, no owner or action — nothing should be created.",
    },

    # ── Direction ───────────────────────────────────────────────────────────
    {
        "id": "direction_l2_l3_priority",
        "kind": "direction",
        "content": (
            "We should prioritize L2 work over L3 for the rest of the quarter — "
            "that's the call, no need to relitigate."
        ),
        "expected": {
            "forbid_create": [{"type": "task", "title_contains": "Prioritize"}],
        },
        "notes": "A leader-direction blurb restating a stance, not a new task ('prioritize L2' is not an action item for the author).",
    },
    {
        "id": "direction_roadmap_musing",
        "kind": "direction",
        "content": (
            "Thinking out loud about how we might restructure the roadmap review "
            "process next half — nothing decided yet."
        ),
        "expected": {
            "forbid_create": [{"type": "task", "title_contains": "Restructure"}],
            "forbid_decision": True,
        },
        "notes": "Explicitly tentative musing ('nothing decided yet') — must not be promoted to a task or a decision.",
    },
]

assert len({f["id"] for f in FIXTURES}) == len(FIXTURES), "fixture ids must be unique"
for _f in FIXTURES:
    assert _f["kind"] in KINDS, f"fixture {_f['id']!r} has unknown kind {_f['kind']!r}"


# ── Scoring ──────────────────────────────────────────────────────────────────

def _entity_type_from_suggestion_type(suggestion_type):
    if suggestion_type and suggestion_type.startswith("create_"):
        return suggestion_type[len("create_"):]
    return None


def _title_matches(title, needle):
    return bool(title) and needle.lower() in title.lower()


def collect_proposed_creates(data):
    """Every entity creation this capture applied or suggested, normalized to
    {"type", "title", "origin"} — the surface precision/recall is scored against.

    `origin` is "applied" (already in the DB) or "suggested" (sitting in the
    review queue). Both count: a bad suggestion is still noise the user has
    to look at and dismiss.
    """
    creates = []
    for change in data.get("applied_changes") or []:
        if change.get("type") == "entity_created":
            creates.append({
                "type": change.get("entity_type"),
                "title": change.get("title") or "",
                "origin": "applied",
                "entity_id": change.get("entity_id"),
            })
    for suggestion in data.get("suggestions") or []:
        entity_type = _entity_type_from_suggestion_type(suggestion.get("suggestion_type"))
        if entity_type is None:
            continue
        payload = suggestion.get("payload") or {}
        title = payload.get("title") or payload.get("statement") or ""
        creates.append({
            "type": entity_type,
            "title": title,
            "origin": "suggested",
            "entity_id": None,
        })
    return creates


def score_fixture(data, expected):
    """Score one capture response against a fixture's `expected` block.

    Returns {"creates", "hits", "misses", "violations"}. `violations` is the
    only thing the test asserts on (forbidden outcomes = precision misses);
    `hits`/`misses` are recall, reported but not asserted — see README.
    """
    creates = collect_proposed_creates(data)

    hits, misses = [], []
    for want in expected.get("must_create", []):
        match = next(
            (c for c in creates if c["type"] == want["type"] and _title_matches(c["title"], want["title_contains"])),
            None,
        )
        (hits if match else misses).append({"want": want, "match": match})

    violations = []
    for forbid in expected.get("forbid_create", []):
        match = next(
            (c for c in creates if c["type"] == forbid["type"] and _title_matches(c["title"], forbid["title_contains"])),
            None,
        )
        if match:
            violations.append({"reason": f"forbidden {forbid['type']} matched: {forbid['title_contains']!r}", "match": match})

    if expected.get("forbid_decision"):
        for suggestion in data.get("suggestions") or []:
            if suggestion.get("suggestion_type") == "create_decision":
                statement = (suggestion.get("payload") or {}).get("statement", "")
                violations.append({
                    "reason": "decision suggestion forbidden for this fixture",
                    "match": {"type": "decision", "title": statement, "origin": "suggested"},
                })

    if expected.get("expect_no_entities"):
        for c in creates:
            violations.append({"reason": "no entities expected at all", "match": c})

    return {"creates": creates, "hits": hits, "misses": misses, "violations": violations}
