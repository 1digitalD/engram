# Engram Requirements Document

**Version:** 1.0  
**Status:** Derived from shipped capabilities (v6 UI on v4 backend)  
**Last updated:** 2026-07-09  
**Audience:** Potential users evaluating or adopting Engram

---

## 1. Purpose

Engram is a **self-hosted personal workspace** for people who run multiple concurrent initiatives with other people. It turns messy input — meeting transcripts, status updates, notes-to-self, pasted links — into **current, accountable work state** that you review and confirm rather than re-type and re-file.

Engram is built for **one operator**: you. Teammates appear throughout the system as people with commitments, mentions, and shared decisions, but they do not log in. Input arrives **by hand** (paste, type, capture); there are no calendar, recorder, or webhook integrations in the current release.

### 1.1 Problem Statement

Operators juggling several initiatives face recurring friction:

- **Capture is easy; keeping state current is not.** A 45-minute meeting transcript contains progress, commitments, decisions, and follow-ups — but extracting and filing them manually costs an evening.
- **Accountability decays.** Commitments made in meetings lose their source, age invisibly, and resurface only when something slips.
- **Context is scattered.** After two weeks away from an initiative, reconstructing "where things stand" requires archaeology across notes, chat, and memory.
- **AI assistance without trust is worse than none.** Silent entity creation, invisible deduplication, and unverifiable summaries erode confidence faster than they save time.

Engram addresses these by preserving every capture as an immutable source artifact, deriving structured work state from it with AI, and requiring human consent for every consequential change.

### 1.2 Success Criteria

A successful Engram deployment means:

- You can paste a multi-topic meeting transcript and, in about a minute of review, have every touched initiative updated with progress, commitments, and decisions — each linked to the original words.
- Opening the app answers, in one glance: **what needs me, who owes me, what's in motion, what happened while I was away.**
- Every commitment has an owner, a source receipt, and visible age. Nothing consequential happens without your say-so.
- "Why did we decide X?" and "what happened on Y in June?" are answerable in seconds, with citations to original captures.
- The system reduces what you hold in your head. Any surface that generates bookkeeping homework has failed.

---

## 2. Scope

### 2.1 In Scope (Current Release)

| Area | Description |
|------|-------------|
| **Capture** | Quick capture from anywhere; paste transcripts, notes, updates, links |
| **Distillation** | One reviewable report per substantive capture |
| **Stream** | Immutable, timestamped log of everything you supplied |
| **Spaces** | Durable work contexts (initiatives, teams, accounts) with optional finish lines |
| **Themes** | Lightweight forward-looking intents promotable to Spaces |
| **Commitments** | Tasks and waiting-ons with owners, due dates, receipts, and status |
| **Decisions** | First-class decision records with participants, quotes, and supersession |
| **People** | Accountability and meeting-prep views per person |
| **Resources** | Documents, links, and artifacts worth keeping addressable |
| **Today** | Morning triage: needs-you vs. in-motion |
| **Workboard** | Portfolio roll-up across all Spaces and people |
| **Dossier** | One-minute re-load view per Space (brief, decisions, commitments, spine) |
| **Review** | Distillation reports, proposals, weekly digest, and the Ledger |
| **Recall** | Hybrid keyword + semantic search from the omnibar |
| **Follow-up markers** | Scheduled nudges and discuss markers on commitments |
| **Nudge drafting** | Receipt-grounded follow-up messages (copy/send is manual) |
| **Meeting prep** | On-demand prep for a person: mutual obligations, decisions, changes |
| **Insights** | Daily exceptions, weekly digest, monthly portfolio health |
| **Trust & audit** | Ledger of all human and AI actions; undo for auto-applied work |
| **Field pinning** | Human edits are authoritative; AI proposes against pinned values |
| **MCP integration** | Write-enabled Model Context Protocol server over `/api/v4` |
| **Self-hosted deployment** | Local Postgres + Flask API + React UI; optional Tailscale access |

### 2.2 Out of Scope (Current Release)

| Area | Notes |
|------|-------|
| Multi-user / collaboration | Single operator only; teammates never log in |
| Calendar / recorder integrations | Transcripts and updates are pasted manually |
| Automatic nudge sending | Drafts are generated; you copy and send via your own channels |
| Agent runs / live run cards | Delegated multi-step agent work is deferred |
| Natural-language standing orders | Per-Space threshold settings ship instead |
| Plan-slip history | Finish-line movement over time is derivable later, not a first-class view |
| Graph view, advanced dashboards | Portfolio health is briefing-style, not chart-heavy |
| Recurring tasks | Not in baseline |
| Roadmap / Gantt product | Themes hold intent, not schedules |
| Public cloud SaaS | Self-hosted by design |

---

## 3. Actors

| Actor | Role |
|-------|------|
| **Operator** | The single Engram user: captures input, reviews AI proposals, manages work state, runs the portfolio |
| **Person (entity)** | Someone who appears in your work — as commitment owner, meeting participant, or mention. Not a login account |
| **AI agents** | Server-side extraction, reconciliation, brief generation, nudge drafting. Always attributed; consequential actions require consent |
| **External agents (MCP clients)** | Claude, Cursor, Codex, or custom tools that read and write via the MCP server — same trust rules as the UI |

---

## 4. Core Concepts

Understanding Engram requires two complementary ideas.

### 4.1 The Stream — What Happened

The Stream is an append-only log of everything you supplied: transcripts, notes, updates, blurbs, pasted links. Stream entries are **immutable** — never edited in place, never converted into something else, never deleted by AI. You may append a correction that links to the original, redact a mispaste, or delete your own entries.

Immutability makes capture zero-decision (nothing at capture time can be "wrong"), makes accountability factual (receipts cannot drift), and makes the work record durable (summaries cite ground truth).

### 4.2 The Fabric — What It Means

The Fabric is the living state of your work, woven from the Stream and continuously reconciled against it:

| Concept | What it is |
|---------|------------|
| **Space** | A durable context — an initiative, team, account, or Home. May have a finish line (outcome + target date) |
| **Theme** | A named intent not yet work ("EU expansion, maybe Q4"). Promotable to a Space with history intact |
| **Commitment** | Something someone said they'd do. Has an owner, due date, status, and receipt. Yours = task; someone else's = waiting-on |
| **Decision** | What was decided, when, with whom, the source quote, and status (active / superseded) |
| **Person** | Aggregated view: open commitments, delivery history, mentions, shared decisions |
| **Resource** | A document, link, or artifact worth keeping addressable |

**Note** is not a managed entity type in the UI — notes are Stream entries. Structure is derived and attached; the entry stays a plain fact.

### 4.3 Relationships

Connections between entities (parent, assigned_to, derived_from, mentions, blocks, etc.) are first-class records, not hidden fields. The UI shows connections with plain-language reasons rather than exposing a relationship taxonomy.

---

## 5. Information Architecture

Six primary surfaces plus persistent chrome:

```
┌────────────────────────────────────────────────────────────────┐
│  CHROME (always present)                                       │
│  · Capture line — one keystroke away, everywhere               │
│  · Omni-bar — Recall search from anywhere                      │
│  · Pulse — pending review count and agent activity summary     │
├────────────────────────────────────────────────────────────────┤
│  TODAY       needs-you vs. in-motion                           │
│  WORKBOARD   portfolio roll-up — all commitments, what's trailing │
│  STREAM      raw capture log, browsable by time                │
│  REVIEW      distillation reports + proposals + Ledger         │
│  SPACES      initiatives & contexts → each opens as a Dossier  │
│  PEOPLE      accountability & prep view per person               │
│  RECALL      omnibar mode — search, not a separate destination │
└────────────────────────────────────────────────────────────────┘
```

The default landing route is **Today** (`/today`).

---

## 6. Functional Requirements

Requirements use **SHALL** for mandatory behavior and **SHOULD** for recommended behavior.

### 6.1 Capture

| ID | Requirement |
|----|-------------|
| CAP-01 | The system SHALL provide a capture line accessible from every surface |
| CAP-02 | Capture SHALL accept free-form text of any length, including multi-topic meeting transcripts |
| CAP-03 | Capture SHALL preserve the original content as an immutable Stream entry before any AI processing |
| CAP-04 | A one-line quick capture SHALL complete in near-zero interaction cost |
| CAP-05 | Substantive captures SHALL trigger distillation and produce exactly one reviewable report |
| CAP-06 | The system SHALL NOT require filing, tagging, or Space selection at capture time |

### 6.2 Distillation

| ID | Requirement |
|----|-------------|
| DIS-01 | Each substantive capture SHALL produce exactly one distillation report, not a scatter of disconnected proposals |
| DIS-02 | Reports SHALL be ordered: routing summary → updates to existing work → new commitments → decisions → open questions → leftovers |
| DIS-03 | Every report item SHALL carry a receipt linking to the source capture (tap → highlighted source lines) |
| DIS-04 | The distiller SHALL search existing Fabric before proposing creation (reconciliation-first) |
| DIS-05 | Near-duplicate commitments SHALL be surfaced as explicit reconciliation questions, not silently merged |
| DIS-06 | Ambiguous speaker attribution SHALL produce attribution questions, not guessed owners |
| DIS-07 | Non-actionable content (scheduling chatter, smalltalk, known-status recap) SHALL be set aside visibly, not silently dropped |
| DIS-08 | Review of a typical meeting report SHOULD be completable in under 90 seconds without opening the raw transcript |
| DIS-09 | Batch-accept of high-confidence remainder SHALL be available in one action |
| DIS-10 | A completed review SHALL land as one undoable change batch |

### 6.3 Stream

| ID | Requirement |
|----|-------------|
| STR-01 | The Stream SHALL present all captures in chronological order |
| STR-02 | Stream entries SHALL NOT be edited in place by AI |
| STR-03 | The operator SHALL be able to redact a Stream entry; redaction SHALL visibly break citations pointing at it |
| STR-04 | The operator SHALL be able to delete their own Stream entries |

### 6.4 Spaces and Dossier

| ID | Requirement |
|----|-------------|
| SPC-01 | Each Space SHALL open as a Dossier providing a one-minute re-load of initiative state |
| SPC-02 | The Dossier SHALL include: header (name, finish line, human-owned status), AI-maintained Brief, decision log, next actions (yours / waiting-on), and chronological Spine |
| SPC-03 | The Brief SHALL be timestamped, regenerable, and every sentence SHALL cite source material |
| SPC-04 | Decisions SHALL show date, participants, receipt, and supersession links |
| SPC-05 | The Spine SHALL interleave captures, distillation events, progress updates, proposals, and human edits with attribution |
| SPC-06 | Spaces MAY have per-Space standing-order threshold settings (e.g., flag waiting-ons idle after N days) |
| SPC-07 | The operator SHALL be able to add a commitment, log an update, and mark done inline on the Dossier without forms |

### 6.5 Themes

| ID | Requirement |
|----|-------------|
| THM-01 | The operator SHALL be able to create a Theme with a name, intent, and optional horizon |
| THM-02 | Themes SHALL hold attached decisions and questions without pretending to be active work |
| THM-03 | Promoting a Theme to a Space SHALL preserve all links, tags, events, and decisions |
| THM-04 | Promotion SHALL write a `promoted` event to the Ledger |
| THM-05 | Themes SHALL appear on the Workboard's forward-looking rail, separate from active commitments |

### 6.6 Commitments

| ID | Requirement |
|----|-------------|
| COM-01 | Every commitment SHALL have an owner, status, and source receipt |
| COM-02 | Commitments owned by the operator SHALL appear as personal tasks |
| COM-03 | Commitments owned by someone else SHALL appear as waiting-ons |
| COM-04 | Age SHALL be visible everywhere a commitment appears |
| COM-05 | The operator SHALL be able to change status, due date, owner, and parent Space inline |
| COM-06 | Human edits to status, due date, title, owner, or parent SHALL pin those fields |
| COM-07 | AI SHALL propose changes to pinned fields when new evidence arrives; it SHALL NOT overwrite them automatically |
| COM-08 | The operator SHALL be able to unpin a field explicitly ("let AI manage this again") |
| COM-09 | A logged update SHALL be amendable in place; prior wording SHALL remain in the Ledger |

### 6.7 Today

| ID | Requirement |
|----|-------------|
| TOD-01 | Today SHALL split content into **Needs you** and **In motion** |
| TOD-02 | Needs you SHALL include: distillation reports awaiting review, your commitments due or overdue, ripened waiting-on follow-ups, blocked questions, and stale items needing a keep/drop/delegate decision |
| TOD-03 | In motion SHALL include: auto-applied annotations (with undo), and resurfaced relevant memories |
| TOD-04 | Ripened follow-ups SHALL be grouped by person with pre-drafted nudges citing original asks |
| TOD-05 | Fired follow-up markers SHALL appear on Today on their due date |
| TOD-06 | Newly at-risk items since yesterday SHALL be listed |

### 6.8 Workboard

| ID | Requirement |
|----|-------------|
| WRK-01 | The Workboard SHALL show every open commitment across all Spaces |
| WRK-02 | Each row SHALL show owner, Space, age, and due date |
| WRK-03 | The operator SHALL be able to filter by state: mine, waiting-on, overdue, stale, blocked, at-risk |
| WRK-04 | The operator SHALL be able to pivot grouping between by-Space and by-person |
| WRK-05 | At-risk flags SHALL be derived signals with a one-line reason and receipt references — not a manually maintained status |
| WRK-06 | Inline actions (nudge, mark done, keep/drop/delegate) SHALL be available on Workboard rows |
| WRK-07 | Archived Spaces and their tasks SHALL be excluded from the Workboard |

### 6.9 People

| ID | Requirement |
|----|-------------|
| PER-01 | Each Person page SHALL aggregate open commitments, delivery history, recent mentions, and shared decisions |
| PER-02 | The People surface SHALL support meeting prep: what you owe them, what they owe you, open shared decisions, discuss markers, and changes since last met — all cited |
| PER-03 | Meeting prep SHALL be available on demand via the omnibar ("prep me for [name]") |

### 6.10 Follow-ups and Nudges

| ID | Requirement |
|----|-------------|
| FUP-01 | Waiting-ons SHALL age visibly and ripen into Today based on per-Space thresholds |
| FUP-02 | The operator SHALL be able to attach follow-up markers to any commitment: nudge (fires on a date), discuss (rides into meeting prep), or custom |
| FUP-03 | Nudge drafts SHALL cite the original ask, date, and source receipt |
| FUP-04 | The system SHALL NOT auto-send nudges; the operator copies and sends via their own channels |
| FUP-05 | A reply or mention in a later capture SHALL reconcile onto the same commitment (proposed mark-delivered via normal distillation) |
| FUP-06 | Markers on archived or completed entities SHALL auto-resolve and never fire |

### 6.11 Review and Ledger

| ID | Requirement |
|----|-------------|
| REV-01 | Review SHALL aggregate distillation reports, pending proposals, the weekly digest, and the Ledger |
| REV-02 | The weekly digest SHALL summarize what moved, was decided, stalled, and is next — cited and editable |
| REV-03 | The weekly digest SHOULD be exportable as a status update without rewriting |
| REV-04 | The Ledger SHALL record every human and AI action with author attribution |
| REV-05 | Auto-applied AI actions SHALL be undoable from the Ledger or inline where they appear |
| REV-06 | Unreviewed proposals SHALL NOT auto-accept; they decay in prominence and roll into the weekly digest |
| REV-07 | Dismissed proposal patterns SHALL be remembered and suppressed on repeat |

### 6.12 Recall (Search)

| ID | Requirement |
|----|-------------|
| REC-01 | Recall SHALL be available from the omnibar on every surface |
| REC-02 | The system SHALL support hybrid keyword + semantic search over entities and captures |
| REC-03 | Search results SHALL be ranked and navigable to the source entity or capture |
| REC-04 | Fragment queries SHALL return instant ranked matches |
| REC-05 | Relevant old entries MAY resurface quietly when opening related work — read-only and dismissible |

### 6.13 Insights

| ID | Requirement |
|----|-------------|
| INS-01 | **Daily** (on Today): exceptions only — ripened follow-ups, fired markers, newly at-risk items |
| INS-02 | **Weekly** (in Review): digest of movement, decisions, stalls, and next steps |
| INS-03 | **Monthly** (on Workboard): portfolio health — quiet people, at-risk Spaces, idle Themes, unowned work |
| INS-04 | Each insight horizon SHALL omit empty sections; a fully empty briefing SHALL say so explicitly |
| INS-05 | Every claim in an insight SHALL cite source material |

### 6.14 Direct Manipulation

| ID | Requirement |
|----|-------------|
| MAN-01 | The operator SHALL be able to change any work-state value through typed inline affordances — no generic "edit entity" forms |
| MAN-02 | Re-homing (move commitment to Space, change owner, attach capture to context) SHALL be one gesture where the item lives |
| MAN-03 | Archive SHALL be instant, inline, and undoable |
| MAN-04 | Delete SHALL require confirmation and write a tombstone Ledger event |
| MAN-05 | Every human edit SHALL be recorded as a Ledger event with attribution |

---

## 7. AI and Trust Requirements

Engram's AI operates with exactly three verbs. Every use of every verb is inspectable.

### 7.1 The Three Verbs

| Verb | Behavior | Examples |
|------|----------|----------|
| **Annotate** | Automatic, marked, undoable | Tagging, routing, linking to existing entities, progress-logging, refreshing briefs |
| **Propose** | Always requires human consent | Creating commitments, decisions, Spaces, people; changing status; merging; deleting |
| **Run** | Delegated, live, interruptible | Multi-step agent work (deferred in current release; outputs still obey Annotate/Propose) |

### 7.2 Trust Rules

| ID | Requirement |
|----|-------------|
| TRU-01 | Entity creation SHALL always be propose-tier; the system SHALL NOT auto-create entities regardless of confidence |
| TRU-02 | Every AI-authored change SHALL be visually marked and attributable to an agent |
| TRU-03 | Every AI action SHALL be one interaction away from its explanation (which agent, what triggered it, reasoning) |
| TRU-04 | Every auto-applied action SHALL be one interaction away from undo |
| TRU-05 | Every claim in a brief, summary, answer, or nudge draft SHALL cite a Stream entry |
| TRU-06 | AI SHALL act on the same objects the user sees — no shadow workspace |
| TRU-07 | Destructive or irreversible work (delete, merge, relationship deletion) SHALL remain reviewable or explicit manual actions |
| TRU-08 | Human edits SHALL pin affected fields; AI reconciliation against pinned values SHALL demote to propose |

### 7.3 Reconciliation

| ID | Requirement |
|----|-------------|
| RECON-01 | The distiller SHALL prefer updating existing Fabric over creating new entities |
| RECON-02 | The same commitment mentioned in multiple captures SHALL be one commitment with multiple receipts |
| RECON-03 | Contradictory decisions SHALL propose supersession, never silent replacement |
| RECON-04 | When uncertain, the system SHALL ask one crisp question rather than guessing loudly |

---

## 8. Integration Requirements

### 8.1 REST API

| ID | Requirement |
|----|-------------|
| API-01 | The runtime API surface SHALL be `/api/v4` only |
| API-02 | The API SHALL support capture, entity CRUD, search, today, workboard, reports, markers, and suggestions |
| API-03 | All relationships SHALL use `EntityLink` records, not embedded IDs in entity properties |

Representative endpoints:

```text
POST /api/v4/capture          — save content, trigger extraction
GET  /api/v4/entities           — list/filter entities
GET  /api/v4/search?q=...       — hybrid keyword + semantic search
GET  /api/v4/today              — Today surface payload
GET  /api/v4/workboard          — portfolio roll-up
GET  /api/v4/reports            — distillation reports
POST /api/v4/reports/<id>/resolve — batch review decisions
```

### 8.2 MCP (Model Context Protocol)

| ID | Requirement |
|----|-------------|
| MCP-01 | Engram SHALL ship a write-enabled MCP server that proxies `/api/v4` |
| MCP-02 | MCP clients SHALL have the same trust rules as the UI — no separate permissions or state |
| MCP-03 | `capture` via MCP SHALL return a `report_id` when distillation creates a report |
| MCP-04 | MCP SHALL expose read tools: search, get entity, list recent, get today, list reports, get workboard |
| MCP-05 | MCP SHALL expose write tools: capture, create/update entity, link entities, accept/dismiss suggestions, resolve reports, add markers, draft nudges |

MCP supports **stdio** (Claude CLI, Cursor, Codex) and **HTTP** (port 8765, including Tailscale Serve).

### 8.3 Operator Identity

| ID | Requirement |
|----|-------------|
| OID-01 | The system SHALL require configuration of which Person entity represents the operator |
| OID-02 | Derived states (mine vs. waiting-on) SHALL depend on operator identity |
| OID-03 | When operator identity is unset, derived states SHALL degrade gracefully with a setup prompt |

---

## 9. Deployment and Operations

### 9.1 Architecture

| Component | Role |
|-----------|------|
| **PostgreSQL + pgvector** | Primary data store with vector embeddings for semantic search |
| **Flask API** | Business logic, extraction pipeline, background jobs |
| **React UI (Vite)** | v6 shell at `/` |
| **MCP server** | Thin proxy for external agent clients |
| **Background worker** | Distillation, embedding, and insight jobs |

### 9.2 Deployment Requirements

| ID | Requirement |
|----|-------------|
| DEP-01 | Engram SHALL be self-hostable on a single machine |
| DEP-02 | Production deployment SHALL bind the API to localhost (default port 5001) |
| DEP-03 | Optional Tailscale Serve SHALL expose API and MCP to the operator's tailnet |
| DEP-04 | Schema changes SHALL be additive-only; production data SHALL be preserved across upgrades |
| DEP-05 | A backup SHALL be taken before any production schema change or deploy |
| DEP-06 | Tests SHALL run against an isolated test database, never production |

### 9.3 Data Safety

| ID | Requirement |
|----|-------------|
| DAT-01 | `flask init-db` SHALL NOT be run against a production database with real data — it wipes all data |
| DAT-02 | Stream entries are the receipts everything else cites; deletion and redaction SHALL be deliberate, visible actions |
| DAT-03 | Entity events (the Ledger) SHALL provide a complete audit trail of mutations |

---

## 10. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | The system SHALL be operable by a single user without IT administration beyond Postgres and Python |
| NFR-02 | Opening Today SHOULD answer the morning triage question in one glance |
| NFR-03 | Opening a Space Dossier after two weeks away SHOULD convey current state in ≤ 1 minute of reading |
| NFR-04 | Daily AI review overhead SHOULD stay near one minute per meeting captured |
| NFR-05 | The UI SHALL NOT expose CRUD-form screens over the entity schema |
| NFR-06 | The UI SHALL NOT maintain a separate notification tray disconnected from the work it concerns |
| NFR-07 | At-risk, stale, and quiet signals SHALL be derived from the record — never manually maintained status fields |
| NFR-08 | Search SHALL combine keyword and semantic retrieval for practical recall across large capture histories |

---

## 11. Entity Model Summary

Supported entity types:

| Type | User-facing role |
|------|------------------|
| `note` | Stream entry (immutable source artifact) |
| `task` | Commitment (with `assigned_to` link for owner) |
| `project` | Space (may have finish line via `due_at`) |
| `area` | Parent context for Spaces |
| `theme` | Forward-looking intent, promotable to project |
| `person` | Someone in your work |
| `resource` | Document, link, or artifact |

Supported relationship types include: `parent`, `related`, `derived_from`, `mentions`, `assigned_to`, `references`, `blocks`, `activity_update`.

---

## 12. What Engram Refuses to Do

These are explicit product boundaries, not backlog items:

- **No filing at capture time.** Filing is the AI's job; consent is the human's.
- **No extraction spam.** One report per capture, reconciliation before creation, near-zero noise floor.
- **No silent deduplication.** Merges and fold-ins are shown so "ignored" never reads as "missed."
- **No invisible AI.** If it acted, it's in the Ledger.
- **No AI assertions without receipts.** Summaries, answers, briefs, nudge drafts — every claim cites the Stream.
- **No second workspace for agents.** One surface, two kinds of hands.
- **No CRUD-form screens.** Direct manipulation is inline, one line, recorded as Ledger events.
- **No roadmap product.** Themes hold intent, not Gantt bars or quarterly planning ceremony.
- **No status anyone has to maintain.** At-risk, stale, quiet — all derived with stated reasons.

---

## 13. Glossary

| Term | Definition |
|------|------------|
| **Stream** | Append-only log of captures (notes) |
| **Fabric** | Derived work state: Spaces, commitments, decisions, people |
| **Space** | A durable work context (stored as `project` or `area`) |
| **Commitment** | A task with an owner and receipt (stored as `task` + `assigned_to`) |
| **Waiting-on** | A commitment owned by someone other than the operator |
| **Finish line** | Target outcome date on a Space |
| **Distillation report** | One reviewable extraction result per capture |
| **Receipt** | Link from a Fabric item to the Stream words that created or updated it |
| **Ledger** | Unified audit log of all human and AI events |
| **Brief** | AI-maintained summary of a Space's current state, fully cited |
| **Spine** | Chronological activity feed on a Dossier |
| **Marker** | A scheduled follow-up attached to a commitment (nudge, discuss, custom) |
| **Pinning** | A human edit that makes a field authoritative over AI reconciliation |
| **Recall** | Hybrid search mode accessible from the omnibar |

---

## 14. Related Documentation

| Document | Purpose |
|----------|---------|
| `docs/ux-vision/UX_VISION.md` | Product vision and design rationale |
| `docs/v6/SOLUTION_DESIGN.md` | Architecture, schema, and trust policy |
| `docs/v6/TEST_PLAN.md` | Use cases and acceptance scenarios |
| `docs/V4_PRINCIPLES.md` | Non-negotiable architecture rules |
| `docs/DEPLOY.md` | Local and Tailscale deployment |
| `mcp_server/README_V4.md` | MCP tool contract |
| `README.md` | Quick start and API examples |
