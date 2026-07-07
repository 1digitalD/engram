# Engram — a UX vision from first principles

*A clean-slate design exercise. This document deliberately ignores the current
implementation and designs the experience from the goals alone. The primary
objective is **cognitive load reduction for someone running multiple
initiatives with other people**: capture anything messy, and the system keeps
progress, commitments, decisions, and follow-ups current — with the human
reviewing, not bookkeeping. AI transparency matters here as the substrate
that makes that delegation safe, not as the headline.*

Mockups referenced throughout live in [`mockups/`](mockups/):

| # | File | What it shows |
|---|------|---------------|
| 1 | [`01-today.html`](mockups/01-today.html) | Today — what needs me, who owes me, what's in motion |
| 2 | [`02-capture-flow.html`](mockups/02-capture-flow.html) | Quick capture, in three time-steps, including async AI enrichment |
| 3 | [`03-review-ledger.html`](mockups/03-review-ledger.html) | Reviewing AI proposals + the Ledger (the trust substrate) |
| 4 | [`04-project-dossier.html`](mockups/04-project-dossier.html) | Working an initiative: brief, decisions, owned next actions, activity spine |
| 5 | [`05-recall.html`](mockups/05-recall.html) | Recall — answers with receipts, trails, and time |
| 6 | [`06-distill-transcript.html`](mockups/06-distill-transcript.html) | **The flagship flow**: a multi-topic meeting transcript distilled into one reviewable report — routed, reconciled, deduplicated |
| 7 | [`07-workboard.html`](mockups/07-workboard.html) | Workboard — the whole portfolio on one screen: every Space, every open commitment, what's trailing |

---

## 1. The job this app is hired for

The operator of Engram runs several concurrent initiatives involving other
people. Their raw material is messy: meeting transcripts spanning multiple
topics and speakers, short status updates, notes-to-self, feedback blurbs.

Scope, stated plainly: **one operator**. Teammates appear everywhere — as
owners, in transcripts, on person pages — but they never log in; this is
the cockpit of the person overseeing the work, not a collaboration suite.
And input arrives **by hand**: transcripts are pasted in, not piped from
recorders or calendars. Both constraints cut enormous accidental scope
(permissions, presence, integrations) and both can be revisited later
without changing the model.

The app's job, stated as outcomes:

1. **I supply whatever I have — the system turns it into current state.**
   Drop in a 45-minute multi-topic transcript and, within a minute of review,
   every initiative it touched is up to date: progress logged, commitments
   captured with owners, decisions recorded, follow-ups armed. My only
   ongoing job is *review and confirm* — never re-typing, re-filing, or
   reconstructing.

2. **At any moment I can see where each initiative stands** — what happened,
   what's decided, what's next, who owes what — in one minute of reading,
   even after two weeks away. And I can see **all of it at once**: one
   screen that rolls up everything the team is on, across every Space and
   person, with what's trailing plainly flagged.

3. **Nothing slips through the cracks.** Every commitment — mine or someone
   else's — has an owner, a source, and an age. Things going quiet get
   surfaced before they become failures, not discovered after.

4. **Accountability without policing.** For each person: what they committed
   to, when, in which meeting, in their own words — so a follow-up is a
   factual, one-click nudge with receipts, not a vague "any update?" and not
   an hour of transcript archaeology.

5. **Planning and follow-up cost minutes, not evenings.** Next steps are
   proposed from actual state; the week starts with a prepared view of what
   needs pushing; meeting prep for any person or initiative is generated on
   demand.

6. **A durable, referenceable work record.** "Why did we decide X?" and
   "what happened on Y in June?" are answered in seconds, with every claim
   citing the original capture. Weekly summaries and status updates draft
   themselves from this record.

7. **No noise, no duplication, no redundancy.** The same commitment mentioned
   in three meetings is one commitment with three receipts. An update about
   an existing task updates it rather than spawning a twin. Chatter and
   smalltalk are visibly set aside, not extracted into clutter.

And one enabling outcome that makes the other seven trustable:

8. **Nothing consequential happens without my say-so, and everything
   automatic is inspectable and reversible.** (§6.)

The litmus test for every screen: **does this reduce what I have to hold in
my head, or does it hand me homework?** Any surface that generates work
instead of absorbing it gets redesigned.

---

## 2. The mental model: a Stream and a Fabric

The user holds two concepts.

### The Stream — what happened

An append-only, timestamped log of everything supplied: transcripts, notes,
updates, blurbs, pasted links, images, things forwarded in by agents. Entries
are **immutable** — never edited in place, never converted into something
else, never deleted by AI. (You can append a correction that links to the
original; only you can delete.)

Immutability is load-bearing for the *primary* job, not just for trust:

- It makes capture zero-decision — nothing you do at capture time can be
  *wrong*, because nothing is committed to except "this happened."
- It makes accountability factual — "Sam committed to this on June 3" links
  to the exact words, and the receipt can't drift out from under the claim.
- It makes the work record durable — summaries and decisions cite ground
  truth that never mutates.

### The Fabric — what it means

The living state of your work, woven *from* the Stream and continuously
reconciled against it:

- **Spaces** — durable contexts (an initiative, a team, an account, Home).
  A Space may have a **finish line** (outcome + target date) — what we'd
  otherwise call a project. Same surface either way; one less filing
  taxonomy. *(Projects and areas collapse into this one container.)*
- **Themes** — the lightest container: a named intent that isn't work yet
  ("EU expansion, maybe Q4"). A name, a sentence of intent, an optional
  horizon, and whatever decisions and questions have attached to it so far.
  When work actually starts, one click **promotes it to a Space** and its
  history comes along. Themes give forward-looking planning a home without
  building a roadmap product — they hold intent, not schedules.
- **Commitments** — the atom of execution: something someone said they'd do.
  Every commitment has an **owner**. Owned by you, it's your task. Owned by
  someone else, it's a **waiting-on** — the unit of accountability. Every
  commitment carries its receipt: who took it on, when, in which capture, in
  what words. Age is always visible.
- **Decisions** — first-class records: what was decided, when, with whom,
  the source quote, and status (active / superseded, with a link to what
  superseded it). Each Space keeps a decision log. This is what makes the
  record *referenceable* rather than merely searchable.
- **People** — everyone who appears in your work. A person page aggregates
  their open commitments, delivery history, recent mentions, and shared
  decisions — the accountability view and the meeting-prep view in one.
- **Resources** — documents, links, artifacts worth keeping addressable.

Two deliberate simplifications of the usual taxonomy:

- **"Note" is not an entity type.** Notes are simply Stream entries. The
  moment "note" becomes a managed object with fields, capture has friction
  again. Structure is *derived* and attached; the entry stays a plain fact.
- **"Task" is subsumed by Commitment.** A to-do you invent for yourself is
  just a commitment you own with yourself as the source. One concept covers
  personal tasks and delegated work, which is exactly what lets "who owes
  what" be a single question.

Typed relationships (parent, blocks, mentions, derived-from, …) survive as
**plumbing, not UI vocabulary**. Users see *connections with plain-language
reasons*; the taxonomy is for agents and queries.

### Who touches what

|  | Stream | Fabric |
|---|---|---|
| **Human** | append, delete own entries | create, edit, delete, anything |
| **AI — automatic** | annotate only (tags, links, routing) | annotate, log matched progress, refresh briefs/summaries |
| **AI — by proposal** | — | create commitments/decisions/spaces/people, change status, merge, unlink, delete |
| **AI — never** | edit, delete, convert entries | act on create/merge/delete/status without approval |

---

## 3. The distillation engine — from messy input to current state

*(Mockup 6 — the flagship flow)*

This is the heart of the app: what happens between "I dropped in a
transcript" and "everything is up to date."

### One capture → one report

A substantive capture (a transcript, long meeting notes, a dense update)
triggers **distillation**. The result is **one reviewable report per
capture** — never a scatter of fourteen disconnected proposals dribbling
into a queue. Because transcripts arrive pasted — in whatever shape the
source tool exported, speaker labels intact, mangled, or absent — the
report *asks* about uncertain attribution ("who committed to this?") as
one of its line items rather than guessing an owner (§9.2). The report
reads top-to-bottom in under a minute:

1. **Routed** — which Spaces this capture touches (a multi-topic meeting
   routes to several; annotate-tier, applied, undoable).
2. **Progress on existing work** — updates *matched to Fabric that already
   exists*: "Sam says landing-page copy is done, QA Thursday" attaches to
   the existing commitment as a progress event. Pure progress-logging is
   annotate-tier; anything that changes state (mark done, move a due date)
   is propose-tier, shown as a diff.
3. **New commitments** — split **yours** vs. **theirs**, each with owner,
   due-ish date, and the quoted words that created it. Propose-tier, always.
4. **Decisions detected** — with participants and the operative quote.
   Propose-tier. If a detected decision contradicts a logged one, the report
   says so and proposes supersession, never silent replacement.
5. **Reconciled, not duplicated** — near-matches surfaced as explicit
   questions: "'Sam: run load tests' looks like existing 'Perf testing
   before GA' — same thing?" One click folds it in (receipts merge); one
   click keeps them separate. The system *shows* its deduplication so the
   user learns to stop double-checking it.
6. **Set aside as noise** — a collapsed line: "scheduling chatter,
   smalltalk, recap of known status — nothing actionable." Visible so that
   *ignored* never reads as *missed*; expandable when the user disagrees,
   and that correction trains the distiller.

The review affordance is calibrated to the content: batch-accept for
high-confidence groups, line-by-line keyboard triage otherwise, edit-in-place
anywhere. Target: **one meeting, one minute**.

### Reconciliation-first, everywhere

The prime directive of every extracting agent: **search the Fabric before
proposing creation.** Updates beat creations; merges beat twins. The same
commitment voiced in three meetings is one commitment with three receipts
and a fresher timestamp — not three entries. Confidence thresholds are
tuned so the noise floor stays near zero: a manager who has to weed
extraction spam will (correctly) stop trusting the system. When in doubt,
the distiller asks one crisp question rather than guessing loudly.

### Quick captures still work the same way

The three-second capture line (Mockup 2) is unchanged — a one-line
note-to-self simply produces a very small distillation (often just routing
chips and maybe one proposed commitment). Capture cost stays near zero at
every input size; review cost scales with substance, sublinearly.

---

## 4. Staying on top: Today, the Workboard, follow-ups, and insights

### Today — the attention instrument *(Mockup 1)*

Two columns; the split is the point:

- **Needs you**: blocked agent questions; distillation reports awaiting
  review; **your commitments** due or overdue; **waiting-on follow-ups that
  have ripened** — grouped by person, aged, each with a pre-drafted nudge;
  and things going stale that need a keep/drop/delegate call.
- **In motion**: live agent runs; a digest of auto-applied annotations (undo
  in place); resurfaced relevant memories.

Opening the app answers, in one glance: *what needs me, who owes me, what's
being handled, what happened while I was away.*

Today is deliberately narrow — it shows what needs attention *now*. The
breadth view is its own surface:

### The Workboard — the whole portfolio on one screen *(Mockup 7)*

Today answers "what needs me"; the Workboard answers **"what is everything
we're working on, and what's trailing?"** It is a roll-up across every
Space and every person: all open commitments (yours and waiting-ons), each
with owner, Space, age, and due-ish date — filterable in one screen by
person, Space, and state (*mine / waiting-on / overdue / stale / blocked /
at-risk*). Grouping pivots between by-Space and by-person, so "what is
Priya carrying across everything?" and "what's open on Acme?" are the same
screen with one toggle.

At-risk is a **derived signal with receipts, not a status field anyone
maintains**: a finish line is flagged when its date is approaching while
its critical commitments are aged or its Spine has gone quiet; a commitment
is flagged when it has aged past the Space's standing-order threshold or
sits blocked on something unresolved. Every flag says *why* in one line —
"finish line Aug 15, two of four open commitments silent 10+ days" — and
clicks through to the evidence. Themes appear here too, as a quiet bottom
rail: named intents with horizons, so forward-looking work stays visible
next to active work without pretending to be in motion.

The Workboard is read-mostly but not read-only: nudge, keep/drop/delegate,
and mark-done are available inline on any row, exactly as they are on Today
and the Dossier.

### The follow-up engine — nothing slips

- Every waiting-on **ages visibly** everywhere it appears. Thresholds are
  set per Space via standing orders ("flag anything idle 5+ days").
- Ripened follow-ups surface on Today with a **drafted nudge built from
  receipts**: *"Hi Sam — checking on the load-test results you mentioned in
  Monday's staff meeting (you estimated Wednesday). Still on track?"* The
  user edits/copies/sends; sending channels are a later integration, but
  drafting from receipts is the leverage.
- A reply or a mention in a later capture **reconciles automatically**: when
  Thursday's transcript says Sam delivered, the waiting-on gets a proposed
  "mark delivered" — the loop closes from ambient input, not manual
  bookkeeping.
- **Meeting prep on demand** (and eventually on calendar signal): ask the
  omni-bar "prep me for Maria" → what you owe her, what she owes you, open
  decisions you share, and what's changed since you last met — all cited.
- Aging and ripening are the *passive* path. There is an explicit one too:
  any commitment can carry a **follow-up marker** — "nudge on Friday,"
  "discuss in next 1:1 with Sam." A marker is one line, human-set, attached
  in place (Today, Workboard, Dossier, or a person page). It fires into
  Today on its date and rides along into meeting prep for its person.
  Passive ripening catches what you forgot to schedule; markers catch what
  you already know needs a date. Both land in the same follow-up queue, so
  there is still only one place to look.

### Insights at three horizons — briefings, not dashboards

The same underlying signals — age, silence, at-risk flags, delivery
history — get **packaged three ways**, matched to how often each is worth
reading:

- **Daily**, on Today: watch items only — ripened follow-ups, fired
  markers, anything newly at-risk since yesterday. Never a report, just
  the day's exceptions.
- **Weekly**, in Review: the digest — what moved, what was decided, what
  stalled, what's next — cited, editable, exportable as a status update.
  The Friday "what did this week even do" reconstruction disappears.
- **Monthly**, on the Workboard: portfolio health — people gone quiet,
  Spaces at risk, Themes idle past their horizon, work nobody owns. The
  slow drifts that no daily view can show.

Each is a short, cited briefing that names what deserves attention and
why — never a wall of charts. If a horizon has nothing to say, it says
nothing.

### The work record — summaries that write themselves

- Each Space keeps an AI-maintained **Brief** (§5) and a **decision log**.
- The weekly digest above drafts itself from the Ledger and the Fabric —
  no one sits down to write it.
- Because every artifact cites the Stream, revisiting any activity or
  decision months later lands on the original words in two clicks.

---

## 5. Working an initiative — the Dossier

*(Mockup 4)*

Opening a Space presents a **Dossier** — the one-minute re-load:

- **Header**: name; finish line if any; a status the *human* owns (AI may
  propose changing it; only the human applies it).
- **The Brief**: AI-maintained — where things stand, open questions, risks.
  Timestamped, regenerable, every sentence cited. The single
  highest-leverage AI artifact in the app: it converts a pile of history
  into a minute of reading.
- **Decisions**: the Space's decision log — most recent first, each with
  date, participants, and receipt; superseded ones struck through with a
  link forward. "Why did we decide X?" lives here.
- **Next actions**: the ordered short list of commitments that move this
  Space, **grouped yours / waiting-on**, with owners and ages visible.
  Delegate-to-agent is one click on any item you own; nudge-with-receipts is
  one click on any item someone else owes.
- **The Spine**: one merged chronological feed — captures routed here,
  distillation events, progress updates, proposals (reviewable inline),
  agent runs, human edits. Human and agent activity interleave, every event
  attributed.
- **Standing orders**: persistent human-written instructions scoped to the
  Space — "watch the Stream for anything about Acme and attach it," "keep
  the Brief fresh," "flag waiting-ons idle 5+ days." Scoped autonomy
  granted in advance, every resulting action attributed back to its order.
- **Fast paths**: capture isn't the only way in. Right on the Dossier (and
  on any commitment row anywhere): **add a commitment**, **log an update**,
  **mark done** — each a single inline line, and each recorded as a
  human-authored **Ledger event**, never a form and never a silent field
  edit. "Mark done" writes "closed by you, here, now" into the record the
  same way a distilled transcript would.

### Direct manipulation — the human's full toolkit

The no-CRUD refusal (§8) bans *form-over-schema screens*, not human
authority over the record. The operator can change anything, in place,
through **typed affordances** — each one specific to what it touches:

- **Status and dates** — inline on any commitment or Space: status,
  due-ish date, follow-up marker. Click the chip, change it, done.
- **Re-homing** — specific moves, never a generic relationship editor:
  move a commitment to a different Space; file a Space under a parent
  context; hand a commitment to a different owner; attach a Stream entry
  to the Space, commitment, or person it belongs with. Each is one
  gesture, offered where the thing lives.
- **Correcting updates** — a logged update can be amended in place; the
  prior wording stays in the Ledger (old → new), so the record never lies
  about what it used to say.
- **Archive and delete** — archive is the everyday verb: instant, inline,
  undoable. Delete is the rare one: confirmed, and recorded as a tombstone
  event. Stream entries are the exception to casual deletion — they are
  the receipts everything else cites — but the operator can still redact
  one (a mispaste, something sensitive); redaction visibly breaks any
  citation that pointed at it rather than silently orphaning claims.

Three invariants keep this from decaying back into CRUD:

1. **Single-purpose, in place.** Every affordance edits one thing where it
   appears. There is no "edit entity" screen, ever.
2. **Everything is a Ledger event.** Human edits are as attributed and
   inspectable as AI actions — same flight recorder, two kinds of hands.
3. **Human edits pin.** A value the operator set by hand is authoritative.
   Reconciliation may *propose* changing it when new evidence arrives —
   "Thursday's transcript suggests this moved to Friday" — but never
   overwrites it automatically, even at annotate tier. And corrections are
   training signal: a re-homed commitment or a fixed owner teaches the
   distiller the same way a dismissal does.

Commitment detail stays lightweight: what, owner, due-ish, receipts,
activity, follow-up marker if any. No twelve-field form, ever.

---

## 6. The trust substrate — why delegation this deep is safe

Everything above asks the user to *stop double-checking*: to trust that a
transcript was fully mined, that dedup worked, that nothing was invented.
That trust has to be earned structurally, not asserted. AI in Engram has
exactly **three verbs**, and every use of every verb lands in one place.

- **Annotate — automatic, marked, undoable.** Low-risk enrichment: tagging,
  routing/linking, progress-logging against existing items, refreshing
  briefs and summaries. Applied instantly, because approving every tag would
  drown the attention this app exists to protect. Three invariants, always:
  **marked** (everything AI-authored wears the spark ✦, one accent color
  reserved app-wide for AI activity), **explained** (one hover from any ✦ is
  the *because*: which agent, triggered by what, reasoning in a sentence),
  **reversible** (one click from any ✦ is undo, indefinitely — and undo is
  a training signal).
- **Propose — always consented.** Creating commitments/decisions/spaces/
  people, changing status, merging, unlinking, deleting. A proposal is **a
  diff with receipts, not a notification**: before → after, quoted source,
  one-line reasoning, confidence. Proposals render inline where they matter
  *and* aggregate (as distillation reports and a Review queue) — control
  never depends on catching things scrolling by. Un-reviewed proposals never
  auto-accept; they decay in prominence and roll into a weekly digest.
  Dismissal is a signal; a repeatedly-dismissed pattern must stop being
  proposed.
- **Run — delegated, live, interruptible.** Multi-step agent work ("chase
  the three open questions," "draft the brief") appears as a live card:
  agent, current step, one-line log, Pause/Stop. A run's *outputs* still
  obey the other two verbs.

The **Ledger** is the flight recorder — every event by every author (human
actions too; it's shared history, not an AI audit log), filterable, with
in-place undo for anything auto-applied. The **Pulse** is its one-line
presence in the chrome: `✦ 2 running · 5 to review` — the permanent answer
to "is something happening right now?"

**The eight rules of the glass box** — screens change, these don't:

1. **One surface.** Agents act on the same objects the user sees — no shadow
   copies.
2. **Attributed.** Every event has an author; AI authorship is always
   visually distinct.
3. **Explained.** Every AI action is one interaction from its *because*.
4. **Reversible.** Every auto-applied action is one interaction from undo.
5. **Consequential means consented.** Create, status, merge, unlink,
   delete — proposed, never applied.
6. **Cited.** Every claim in an answer, brief, or summary links to Stream
   entries. No receipts, no claim.
7. **Interruptible.** Any run can be paused or stopped from anywhere it's
   visible.
8. **Human edits win.** A value set by hand is pinned — AI may propose
   against it with new evidence, but never overwrites it automatically.

---

## 7. Information architecture

Six surfaces plus three persistent chrome elements — the IA fits in one
breath:

```
┌────────────────────────────────────────────────────────────────┐
│  CHROME (always present)                                       │
│  · Capture line — one keystroke away, everywhere               │
│  · Omni-bar — search / ask / prep-me-for, everywhere           │
│  · Pulse — "✦ 2 running · 5 to review", expandable peek        │
├────────────────────────────────────────────────────────────────┤
│  TODAY      needs-you (incl. ripened follow-ups) vs. in-motion │
│  WORKBOARD  portfolio roll-up — all commitments, all Spaces,   │
│             what's trailing; Themes rail for what's ahead      │
│  STREAM     the raw capture log, browsable by time             │
│  REVIEW     distillation reports + proposals + the Ledger      │
│  SPACES     initiatives & contexts → each opens as a Dossier   │
│  PEOPLE     accountability & prep view per person              │
│  (RECALL)   not a place — a mode of the omni-bar, everywhere   │
└────────────────────────────────────────────────────────────────┘
```

Recall itself *(Mockup 5)*: one omni-bar, no mode switch — fragments give
instant ranked matches; questions give **answers with receipts** (every
claim cites an entry; the AI states what it *couldn't* find rather than
fabricating). Every result offers **trails** — temporal neighbors,
connections, follow-up questions — because memory is associative and "I
know it's in there" needs more than one door. Time is a first-class axis:
the Stream scrubs by period and by landmark ("around the Berlin trip").
And recall also comes to you: relevant old entries resurface quietly when
you open related work — read-only, dismissible, never a proposal.

No settings-as-a-destination, no tag manager, no relationship editor. Those
exist as flows inside these surfaces, not as places.

---

## 8. What this vision refuses to do

- **No filing at capture time.** Filing is the AI's job; consent is the
  human's.
- **No extraction spam.** Reconciliation before creation; confidence
  thresholds tuned for near-zero noise; one report per capture, not a
  proposal firehose. If daily review exceeds ~a minute per meeting, the
  system — not the user — is what gets fixed.
- **No silent dedup either.** Merges and fold-ins are shown, so "ignored"
  never reads as "missed."
- **No invisible AI.** If it acted, it's in the Ledger, wearing the spark.
- **No notification tray.** AI activity surfaces in context or in Review —
  always attached to the thing itself.
- **No AI assertions without receipts.** Summaries, answers, briefs, nudge
  drafts — every claim cites the Stream.
- **No second workspace for agents.** One surface, two kinds of hands.
- **No CRUD-form screens.** If a screen looks like a form over a schema,
  the design has failed at that spot. Direct manipulation lives in the
  fast paths — inline, one line, recorded as Ledger events.
- **No roadmap product.** Themes hold a name, an intent, and a horizon —
  no Gantt bars, no swimlanes, no quarterly planning ceremony. When a
  theme becomes work, it becomes a Space.
- **No status anyone has to maintain.** At-risk, stale, quiet, trailing —
  all derived from the record with a stated reason, never a dropdown
  someone forgets to update.

---

## 9. Open questions for the next pass

1. **Extraction precision vs. recall.** "Nothing slips" pulls toward
   aggressive extraction; "no noise" pulls toward conservatism. The
   distillation report's "set aside as noise" line is the pressure valve —
   but the thresholds, and how fast user corrections retune them, need
   real-transcript validation.
2. **Speaker identity in transcripts.** Commitments-with-owners depend on
   knowing who said what. How does the system handle unattributed or
   misattributed speakers — and how does it ask for help without becoming a
   chore?
3. **Nudge tone and cadence.** Drafted follow-ups must land as helpful, not
   surveillance. Per-person tone preferences? Minimum intervals?
4. **Proposal volume at scale.** Batching, standing-order scoping, and
   confidence tuning to keep review under a minute a day across many active
   Spaces.
5. **Undo semantics at depth.** Undoing an annotation is trivial; unwinding
   an accepted merge weeks later is not. The Ledger makes everything
   *visible*; how far back everything stays *reversible* needs definition.
6. **How many agents does the user perceive?** One assistant persona vs. a
   small named cast (distiller, project-keeper, researcher). Start small and
   watch whether names carry meaning or noise.
7. **At-risk calibration.** The Workboard's derived flags face the same
   precision/recall tension as extraction: flag too early and "at-risk"
   becomes wallpaper; too late and it's a post-mortem. What the default
   heuristics are (days quiet vs. finish-line proximity vs. blocked
   chains), and how standing orders override them per Space, needs a pass
   with real portfolios. Plan-slip history (how a finish line moved over
   time) is deliberately deferred — the record makes it derivable later.

---

## 10. Adopted build stance (decided 2026-07-07)

The document above is clean-slate by design. Reviewing it against the v4
codebase produced these decisions, recorded here so the next planning pass
starts from them:

- **The backend substrate stays.** The v4 data model maps almost
  one-to-one onto this vision: `note`→Stream entry, `project`+`area`→Space,
  `task`+`assigned_to`→Commitment, `Decision` as-is, `EntityEvent`+
  `ChangeBatch`→Ledger, `AiSuggestion`→proposals, plus search, embeddings,
  brief, attention, and MCP services. Renames live in the UI vocabulary
  and DTOs, **not** the database — schema changes remain additive-only per
  `docs/V4_PRINCIPLES.md`.
- **The UI is rebuilt clean.** A new app shell implementing this IA talks
  to the existing `/api/v4`; the legacy views, the V5 generation, and the
  `/lab` surface are retired (not extended) once Today + Review + Dossier
  reach parity. Three additive UI strata was the failure mode; a fourth is
  not the fix.
- **Auto-create at confidence ≥0.9 is retired** in favor of rule 5
  (consequential means consented). It ships in the same change as the
  distillation report's batch-accept — one without the other makes review
  worse, not better.
- **Deferred from scope**: agent runs / the Pulse's run cards (the ✦
  conventions stay so they can land later), natural-language standing
  orders (per-Space threshold *settings* ship instead), sending channels
  for nudges, calendar/recorder integrations, plan-slip history.
- **Build order**: distillation report quality first (it is the load-
  bearing bet; measure review-time-per-meeting with the existing replay
  eval), Workboard early (cheap — it's queries over data `/today` already
  computes), then Dossier + direct manipulation, then markers, Themes,
  and insight horizons.
