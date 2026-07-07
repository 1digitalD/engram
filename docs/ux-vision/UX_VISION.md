# Engram — a UX vision from first principles

*A clean-slate design exercise. This document deliberately ignores the current
implementation and designs the experience from the stated goals alone:
frictionless capture, effortless recall, AI-leveraged project work, and a UI
that is a genuinely shared surface between one human and their agents.*

Mockups referenced throughout live in [`mockups/`](mockups/):

| # | File | What it shows |
|---|------|---------------|
| 1 | [`01-today.html`](mockups/01-today.html) | Today — the attention surface ("needs you" vs. "in motion") |
| 2 | [`02-capture-flow.html`](mockups/02-capture-flow.html) | Capture, in three time-steps, including async AI enrichment |
| 3 | [`03-review-ledger.html`](mockups/03-review-ledger.html) | **AI activity surfacing for human review** — the proposal queue and the Ledger |
| 4 | [`04-project-dossier.html`](mockups/04-project-dossier.html) | Working a project, with inline proposals and a live agent run |
| 5 | [`05-recall.html`](mockups/05-recall.html) | Recall — answers with receipts, trails, and time |

---

## 1. The outcomes this app must deliver

Everything below is derived from four fixed goals: near-zero-friction capture,
effortless recall, AI-assisted project/task execution, and trustable
human+agent co-operation on one surface. Stated as jobs-to-be-done:

1. **Set a thought down in under three seconds, from anywhere in the app,
   with zero filing decisions.** Capture must cost less than the thought is
   worth, or it won't happen. No form, no folder, no type picker, no tags —
   type, enter, gone.

2. **Trust that the system caught it.** A capture is visibly acknowledged,
   asynchronously enriched, and never lost, silently mutated, or silently
   converted into something else. The user should stop keeping backup copies
   in their head.

3. **Open the app and know, within ten seconds: what needs me, what the AI
   already handled, and what's in motion right now.** The home surface is an
   attention instrument, not a dashboard of database tables.

4. **Nothing consequential happens without my say-so — and everything
   automatic is inspectable and reversible.** Creating entities, changing
   status, deleting, merging, unlinking: always a reviewable proposal. Tags,
   metadata, links: applied automatically but always attributed, explained,
   and one click from undo.

5. **Recall the way memory actually works: by fragment, association, and
   time — and get answers with receipts.** "That thing about pricing from
   around when I was talking to Maria" must work. Every AI-synthesized answer
   cites the captures it came from.

6. **Run a project by steering, not bookkeeping.** The AI keeps the summary,
   status, next actions, and loose ends fresh; the human makes the calls.
   Opening a project after two weeks away should take one minute to re-load
   into your head, not twenty.

7. **Delegate work to agents and watch it happen — live, attributable,
   interruptible — in the same place I do my own work.** Agent activity is
   not a background process or a notifications tray; it is a colleague
   working in the same room.

A useful litmus test for every screen: **does this feel like a second brain
with a competent assistant inside it, or like a database UI with forms bolted
on?** Any surface that fails the test gets redesigned.

---

## 2. The mental model: a Stream and a Fabric

The user should hold exactly two concepts in their head.

### The Stream — what happened

An append-only, timestamped log of everything captured: thoughts, pasted
links, images, meeting notes, snippets forwarded in by agents. Entries in the
Stream are **immutable**. They are never edited in place, never converted
into something else, never deleted by AI, never re-filed. (You can append a
correction that links to the original, and you — never an agent — can delete
an entry.)

Immutability isn't a technical nicety here; it is load-bearing for trust:

- It's what lets capture be zero-decision — nothing you do at capture time
  can be *wrong*, because nothing is being committed to except "this
  happened."
- It's what makes AI answers citable — a citation to an immutable entry means
  the receipt can't drift out from under the claim.
- It's what makes "the AI never silently changed my stuff" checkable rather
  than a promise.

### The Fabric — what it means

Structure woven *from* the Stream: **Tasks**, **Spaces** (see below),
**People**, and **Resources**, connected by relationships. Every piece of
Fabric carries a visible thread back to the Stream entries it was derived
from — structure always shows its receipts. Fabric is freely editable (with
history), because meaning changes even when the record doesn't.

Two deliberate simplifications of the current entity taxonomy:

- **"Note" is not an entity type.** Notes are simply Stream entries. The
  moment "note" becomes a managed object with fields and status, capture has
  friction again. Anything note-like that needs structure gets *derived*
  Fabric attached to it, while the entry itself stays a plain fact in the log.
- **Projects and Areas collapse into one container: the Space.** A Space is a
  durable context (Health, Home, Acme Corp). A Space may have a **finish
  line** — an outcome and a target — which is what we used to call a project.
  Same surface, same behaviors; a finish line adds a goal header, progress,
  and an "is this done yet?" lifecycle. This halves the taxonomy the user
  must learn and eliminates the perennial "is this a project or an area?"
  filing dilemma — another decision deferred instead of demanded.

Typed relationships (parent, blocks, mentions, derived-from, …) survive, but
as **plumbing, not UI vocabulary**. The user sees *connections with
plain-language reasons* ("linked because this capture mentions Maria and the
Q3 deck"). The type taxonomy is for agents and queries; humans get sentences.

### Who touches what

|  | Stream | Fabric |
|---|---|---|
| **Human** | append, delete own entries | create, edit, delete, anything |
| **AI — automatic** | annotate only (tags, metadata, links) | annotate + refresh summaries |
| **AI — by proposal** | — | create, status change, merge, unlink, delete |
| **AI — never** | edit, delete, convert entries | act on merge/delete/status without approval |

---

## 3. The trust architecture: a glass box

AI in Engram has exactly **three verbs**, and every use of any verb lands in
one place, the **Ledger**.

### Annotate — automatic, marked, undoable
Low-risk enrichment: tagging, extracting metadata (dates, people, URLs),
linking related items, refreshing an AI-maintained summary. Applied
instantly, because making the user approve every tag would drown the very
attention the app exists to protect. But three invariants hold, always:

- **Marked.** Everything AI-authored wears the spark (✦) and is visually
  distinct — one consistent accent color used *only* for AI activity, across
  the whole app. Human-authored and AI-authored content are never
  indistinguishable.
- **Explained.** One hover/tap from any ✦ gets you the *because*: which
  agent, when, triggered by what, reasoning in one sentence.
- **Reversible.** One click from any ✦ is Undo — indefinitely, from the item
  itself or from the Ledger. Undo is also a training signal: reverted
  annotations teach the annotator.

### Propose — always consented
Anything consequential: creating a task/space/person/resource, changing a
status, merging, deleting, removing a relationship. A proposal is **a diff,
not a notification**: before → after, the source entry it derives from
(quoted), the agent's one-line reasoning, and its confidence. Proposals
render **inline where they matter** (on the capture, in the project spine, on
the task) *and* aggregate into a Review queue — the user never has to go
somewhere else to stay in control, but can go one place to catch up.
Un-reviewed proposals never auto-accept; they decay in prominence and roll up
into a weekly digest instead of nagging.

### Run — delegated, live, interruptible
Multi-step agent work the user hands off ("draft the brief," "chase down the
three open questions in this space"). A run is a **live card**: which agent,
acting on what, current step, a scrolling one-line log, elapsed time, and
Pause / Stop controls. Run cards appear in Today's "In motion" column and in
the spine of whatever Space the work belongs to. A run's *outputs* still obey
the other two verbs — a run that wants to create three tasks produces three
proposals, not three tasks.

### The Ledger and the Pulse
The **Ledger** is the flight recorder: every annotate/propose/run event, by
every agent, forever — filterable by agent, verb, object, and time, with undo
available in place for anything auto-applied. The **Pulse** is its persistent
one-line presence in the app chrome: `✦ 2 running · 5 to review`. Always
visible, glanceable, expandable to a peek panel from anywhere. The user never
wonders "is something happening right now?" — the answer is permanently on
screen.

### The seven rules of the glass box
1. **One surface.** Agents act on the same objects the user sees — no shadow
   copies, no separate "AI workspace."
2. **Attributed.** Every event has an author chip; AI authorship is always
   visually distinct.
3. **Explained.** Every AI action is one interaction away from its *because*.
4. **Reversible.** Every auto-applied action is one interaction away from
   undo, indefinitely.
5. **Consequential means consented.** Create, status, merge, unlink, delete —
   proposed, never applied.
6. **Cited.** AI never asserts from thin air: every claim in a synthesized
   answer or AI-maintained summary links to Stream entries.
7. **Interruptible.** Any running agent can be paused or stopped from
   anywhere it is visible.

These rules are the product. Screens change; these don't.

---

## 4. Information architecture

Five surfaces, plus three persistent chrome elements. Deliberately small: the
IA fits in one breath.

```
┌────────────────────────────────────────────────────────────────┐
│  CHROME (always present)                                       │
│  · Capture line — one keystroke away, everywhere               │
│  · Omni-bar — search + ask, everywhere                         │
│  · Pulse — "✦ 2 running · 5 to review", expandable peek        │
├────────────────────────────────────────────────────────────────┤
│  TODAY      the attention surface: needs-you vs. in-motion     │
│  STREAM     the raw capture log, browsable by time             │
│  REVIEW     proposal queue + the Ledger (AI flight recorder)   │
│  SPACES     list of contexts → each opens as a Dossier         │
│  (RECALL)   not a place — a mode of the omni-bar, from anywhere│
└────────────────────────────────────────────────────────────────┘
```

**Why each surface exists:**

- **Today** exists because outcome #3 ("what needs me?") deserves the front
  door, and because it is where AI activity meets human attention — the two
  columns *are* the trust model made spatial.
- **Stream** exists because the raw record must be browsable as itself —
  unfiled, chronological, honest. It's the surface that proves nothing was
  lost or mutated.
- **Review** exists so control never depends on catching things as they
  scroll by. Inline proposals keep you in flow; Review lets you catch up
  after a day away, keyboard-first.
- **Spaces** exist because sustained work needs a home with memory — the
  Dossier (§5.3).
- **Recall is a mode, not a page**, because the moment recall requires
  navigation it has friction. One keystroke, ask, answer — from anywhere.

Nothing else. No settings-as-a-destination, no tag manager, no relationship
editor. Those exist, but as flows inside these surfaces, not as places.

---

## 5. The interaction model

### 5.1 Capture — set it down, don't file it
*(Mockup 2)*

- **One keystroke anywhere** summons the capture line (it also sits
  permanently at the top of Today and Stream). Type. Enter. A quiet "caught"
  acknowledgment. Total cost: under three seconds, zero decisions.
- **Anything pastes**: text, URLs, images, files. An entry is whatever you
  set down.
- **Hints, never gates.** As you type, the AI may float a ghost chip below
  the line — *"looks like a task for Acme"* — accept it with Tab if you want
  the head start, ignore it and it vanishes. Nothing at capture time is ever
  required, and nothing you skip is lost — the same inference happens after
  capture anyway.
- **Optional fast paths** for people who want them: leading `todo:` or a
  slash-verb pre-shapes the entry. Power feature, never taught in the
  critical path.
- **Enrichment arrives asynchronously.** Seconds later, the entry in the
  Stream grows ✦-marked chips: tags, extracted dates and people, links to
  related items (annotations — applied, undoable). Anything consequential the
  AI saw in the entry — "this contains a task" — appears as a **pending
  proposal chip** on the entry, visibly different from applied annotations.
  The entry itself never changes.

Capture is also **the agents' door**: an agent forwarding a web page, an
email, or a meeting transcript appends Stream entries the same way, wearing
its author chip. One log, two kinds of authors — rule 1.

### 5.2 Triage and review — control without vigilance
*(Mockup 3 — the required AI-review flow)*

- **Proposals appear inline first.** On the capture that spawned them, in the
  Space spine they affect, on the task whose status would change. Accept or
  dismiss right there, in flow.
- **Review is the catch-up surface.** All pending proposals, grouped by
  provenance ("From: Tuesday's meeting note — 3 proposals") because
  provenance-siblings share a fate — if the meeting note was real, its three
  extracted tasks probably all are. Keyboard-first: `↵` accept, `e` edit then
  accept, `⌫` dismiss, `j/k` move. Triaging ten proposals should take under
  a minute.
- **Every proposal is a diff with receipts**: before → after, quoted source
  excerpt with a link to the full entry, agent, one-line reasoning,
  confidence. High-confidence groups offer batch-accept; anything the AI is
  unsure about says so and never batches.
- **Dismissal is a signal**, not a shrug: dismissed proposals feed back to
  the proposing agent, and a repeatedly-dismissed pattern should stop being
  proposed.
- **The Ledger tab** completes the loop: the full record of everything
  applied automatically, with in-place undo, plus every proposal's outcome
  and every run's transcript. Filter by agent to answer "what has the
  research agent been doing all week?" in one view.

### 5.3 Working a Space — the Dossier
*(Mockup 4)*

Opening a Space presents a **Dossier** — the one-minute re-load of context:

- **Header**: name; if it has a finish line, the outcome, target date, and a
  status the *human* owns (AI may propose changing it; only the human applies
  it).
- **The Brief** (left): an AI-maintained summary — where things stand, open
  questions, loose ends. Prominently ✦-marked, timestamped ("as of 2h ago"),
  regenerable on demand, and every sentence in it cites the Stream entries
  and events it summarizes (rule 6). The Brief is the single highest-leverage
  AI artifact in the app: it converts a pile of history into a minute of
  reading.
- **Next actions** (left): the ordered short list of tasks that move this
  Space. Each task can be **delegated** — a `Delegate ▸` control hands it to
  an agent and swaps the row into a live run chip.
- **The Spine** (right): one merged, chronological feed of everything in this
  Space — your captures that were linked here, agent annotations, proposals
  (reviewable inline, right in the feed), run cards, status changes, human
  edits. The Spine is where "shared surface" is most literal: human and agent
  events interleave in one timeline, every one attributed.
- **Standing orders**: persistent, human-written instructions scoped to the
  Space — "watch the Stream for anything about Acme and attach it," "keep
  the Brief fresh weekly," "flag tasks idle >7 days." Standing orders are
  how autonomy gets *scoped by the human in advance* rather than begged for
  action-by-action. They are visible, editable, and every action they cause
  is attributed back to them ("via standing order: watch for Acme").

Tasks themselves stay lightweight — a title, an optional due date, a Space, a
state (open / doing / done / dropped), and their receipts. The task *detail*
view is just a small dossier: description, its source thread, its activity.
No twelve-field task form, ever.

### 5.4 Recall — ask like you remember
*(Mockup 5)*

- **One omni-bar, two intents, no mode switch.** Type fragments, get instant
  matches (entries, tasks, spaces, people) ranked by association with what
  you're doing now. Phrase a question, get an **answer with receipts**: a
  synthesized paragraph where every claim carries a citation chip to a Stream
  entry — click to see the original in context. No citation, no claim.
- **Trails, because memory is associative.** Beside any result: what was
  captured *around the same time*, what *links to it*, what *else mentions
  these people*. The failure mode of every notes app — "I know it's in there
  but I can't find the door" — is solved by giving every result three more
  doors.
- **Time is a first-class axis.** The Stream scrubs by period ("March",
  "around the Berlin trip"), because "when-ish" is often the strongest key
  a human still holds.
- **Resurfacing: recall that comes to you.** When you open a Space or start
  a task, relevant old entries surface quietly ("from your stream, last
  November"). Read-only, dismissible, never a proposal — the system acting
  like a colleague with a good memory, not an eager filer.

### 5.5 Today — the attention instrument
*(Mockup 1)*

Two columns, and the split *is* the point:

- **Needs you**: agent questions (blocked runs asking for a decision — the
  highest-priority item type in the app, because a waiting agent is wasted
  leverage), a digest of pending proposals, today's and overdue tasks, and
  things going stale (commitments idle so long they need a human call).
- **In motion**: live run cards, a "while you were away" digest of
  auto-applied annotations (with undo right in the digest), and gentle
  resurfacings.

Capture line on top; Pulse in the chrome. Opening the app answers, in one
glance: *what needs me, what's being handled, what happened while I was
gone.* Nothing on Today is a table.

---

## 6. What this vision refuses to do

Stances worth recording as explicitly as the features:

- **No filing at capture time.** Every "which project? what type? which
  tags?" moment is friction compounding into abandonment. Filing is the AI's
  job, consent is the human's.
- **No invisible AI.** No background process quietly improving things. If it
  acted, it's in the Ledger, wearing the spark.
- **No notification tray.** Notifications-as-a-list is where trust goes to
  die. AI activity surfaces *in context* (inline chips, spine events, run
  cards) or *in the Review queue* — always attached to the thing itself.
- **No AI assertions without receipts.** Summaries, answers, briefs — every
  claim cites the Stream.
- **No second workspace for agents.** One surface, two kinds of hands.
- **No entity-forms UI.** If a screen ever looks like a CRUD form over a
  schema, the design has failed at that spot and gets reworked.

---

## 7. Open questions for the next pass

Deferred deliberately — they need validation, not more design:

1. **Proposal volume tuning.** The whole model lives or dies on the review
   queue staying under ~a minute a day. What confidence thresholds, batching,
   and standing-order scoping keep it there in real use?
2. **How many agents does the user perceive?** One assistant persona vs. a
   visible cast of specialists (annotator, researcher, project-keeper).
   Attribution design differs; start with a small named cast and watch
   whether names carry meaning or noise.
3. **Undo semantics at depth.** Undoing an annotation is trivial; undoing an
   accepted merge weeks later is not. The Ledger makes everything *visible*;
   how far back everything stays *reversible* needs definition.
4. **Stream scale.** At 50k entries, does the chronological Stream stay a
   surface people visit, or does it become pure substrate for Recall? Both
   are fine — but the answer changes how much design the Stream deserves.
