# Engram PRD: AI-Assisted Productivity Operating System

## 1. Product vision

Engram is an **AI-assisted personal productivity operating system**.

The user should be able to capture raw thoughts, updates, meeting notes, ideas, tasks, decisions, links, and reflections in natural language. Engram should then interpret that input and automatically organize it across:

```text
Projects
Areas
Tasks
Notes
Resources
People
```

The user should not have to manually maintain a complex productivity database. AI should act as a system maintainer that keeps projects, tasks, areas, resources, people, and notes organized over time.

The UI should not be the primary input mechanism. The primary input mechanism is **capture**.

The UI exists to help the user:

```text
Review
Correct
Understand
Search
Directly manage
Make sense of relationships
Act on what matters today
```

Engram should feel like:

```text
Capture naturally.
AI organizes intelligently.
User reviews and corrects when needed.
The system stays useful over time.
```

---

# 2. Product principles

## 2.1 Capture first

The user should be able to submit updates without deciding up front whether something is a note, task, project, resource, or area.

Example:

```text
Met Sarosh today. Need to push back on moving Sanket to Deals because it risks memory migration and telemetry. Also ask Sanket for an estimate on the backfill work.
```

Expected behavior:

```text
Create source note.
Detect people: Sarosh, Sanket.
Find existing projects: Agent Memory Migration, Agent Telemetry.
Create or update tasks.
Link everything to the source note.
Show what changed.
```

## 2.2 AI maintains the system, not just creates entities

AI must not blindly create new entities every time it detects something.

The AI pipeline must first search existing entities and decide whether to:

```text
Update existing entity
Link existing entity
Append context to existing entity
Complete existing task
Reopen existing task
Add follow-up
Change status
Create new entity
Create suggestion for review
Do nothing
```

Core rule:

```text
Prefer updating or linking existing entities over creating new entities.
Create new entities only when no suitable existing match exists.
Suggest instead of creating when uncertain.
```

## 2.3 Notes remain notes

A note should never be silently converted into a task, project, resource, area, or person.

A note is the source artifact. It preserves the original captured context.

Allowed:

```text
Note generates task.
Note mentions person.
Note references resource.
Note updates project.
Note links to area.
```

Disallowed:

```text
Changing note.type from note to task automatically.
Deleting the original note after extraction.
Replacing the note with extracted entities.
Hiding the note behind generated objects.
```

## 2.4 Relationships are infrastructure, not a separate product object

There should be one relationship system:

```text
entity_links
```

Do not create a parallel concept called:

```text
connections
connection model
note_links
project_links
task_person_links
```

The UI may use labels like:

```text
Linked Context
Relationships
Backlinks
Related Items
```

But all of these must read from and write to the same relationship model.

## 2.5 PARA is a lens, not the whole architecture

Engram supports PARA-like organization:

```text
Projects = active outcomes
Areas = ongoing responsibilities
Tasks = actions
Notes = captured thinking/context
Resources = reusable reference material
People = human context
```

But Engram should not become a rigid PARA folder system.

The actual architecture is a flexible entity graph with AI-assisted interpretation and maintenance.

---

# 3. Entity model

The system supports only these primary entity types:

```text
note
task
project
area
resource
person
```

No new primary entity types should be added as part of this work.

## 3.1 Shared base fields

Every entity should support these common fields where applicable:

```text
id
type
title
content / description
status
lifecycle
active / archived state
follow_up_at
due_at
created_at
updated_at
source
reference_url
properties
ai_meta
ai_status
```

## 3.2 Entity meanings

### Note

A note is captured context.

Examples:

```text
Meeting notes
Reflections
Ideas
Status updates
Observations
Decision context
Raw thoughts
```

A note may generate or link to multiple entities.

A note should remain intact.

### Task

A task is an actionable item.

Examples:

```text
Send staffing tradeoff note to Sarosh
Ask Sanket for memory backfill estimate
Review resource cleanup proposal
Book doctor appointment
```

Tasks may belong to projects or areas.

### Project

A project is an active outcome with an end state.

Examples:

```text
Agent Memory Migration
Chat UI Table Review
Launch Engram MVP
Plan India Trip
```

A project should usually have at least one next action unless completed, blocked, or waiting.

### Area

An area is an ongoing responsibility with no final completion point.

Examples:

```text
Agent Platform
Health
Career
Finances
Marriage
Home
Learning
```

Areas contain recurring responsibilities, routines, active projects, resources, notes, and people.

### Resource

A resource is reusable reference material.

Examples:

```text
Article
URL
PDF
Internal doc
Architecture guide
Workout plan
System design template
```

Resources should be linked to the projects, areas, notes, or tasks they support.

### Person

A person represents human context.

Examples:

```text
Sarosh
Sanket
Himmat
David
Recruiter
Doctor
```

People are useful because they are linked to tasks, notes, projects, areas, and resources.

Do not turn People into a full CRM.

---

# 4. Relationship model

## 4.1 Single relationship primitive

All relationships must use the existing universal relationship mechanism.

Recommended table/model:

```text
entity_links
```

Required relationship fields:

```text
id
src_id
dst_id
link_type
inverse
source
confidence
evidence
created_at
updated_at
```

## 4.2 Required relationship types

Use this controlled set:

```text
parent
related
references
blocks
mentions
derived_from
assigned_to
```

Do not create dozens of relationship types unless explicitly needed.

## 4.3 Relationship semantics

### `parent`

Structural containment or ownership.

Examples:

```text
Task parent Project
Project parent Area
Task parent Area
Resource parent Area
```

UI labels:

```text
Belongs to project
Part of area
Filed under area
```

### `derived_from`

Created from another entity, usually a note.

Examples:

```text
Task derived_from Note
Project derived_from Note
Resource derived_from Note
Area derived_from Note
Person derived_from Note
```

UI labels:

```text
Created from note
Generated from
Extracted from
```

### `mentions`

An entity references another entity in content.

Examples:

```text
Note mentions Person
Note mentions Project
Note mentions Area
```

UI label:

```text
Mentions
```

### `references`

An entity cites or uses another as source/reference.

Examples:

```text
Note references Resource
Task references Resource
Project references Resource
```

UI labels:

```text
References
Uses resource
Source
```

### `related`

General association when no stronger relationship applies.

Do not overuse this.

### `assigned_to`

Human ownership or responsibility.

Examples:

```text
Task assigned_to Person
Project assigned_to Person
```

UI labels:

```text
Assigned to
Owned by
Involves
```

### `blocks`

Dependency relationship.

Examples:

```text
Task blocks Task
Project blocks Project
```

UI labels:

```text
Blocks
Blocked by
```

---

# 5. AI interpretation pipeline

## 5.1 Core flow

Every natural-language capture should follow this flow:

```text
1. Save original capture as a note/source artifact.
2. Interpret the capture.
3. Detect candidate entities.
4. Search existing entities.
5. Reconcile detected entities against existing entities.
6. Decide proposed operations.
7. Auto-apply safe high-confidence operations.
8. Store medium-confidence operations as suggestions.
9. Avoid low-confidence mutations.
10. Link all changes back to the source note.
11. Show user what changed and allow correction/undo.
```

## 5.2 Interpretation output

The AI should produce a structured change plan.

Example shape:

```json
{
  "source_note_id": "note_123",
  "capture_summary": "Meeting update about staffing risk",
  "capture_type": "project_update",
  "detected_entities": [
    {
      "type": "person",
      "name": "Sarosh",
      "matched_entity_id": "person_001",
      "match_confidence": 0.97,
      "operation": "link_existing_entity"
    },
    {
      "type": "person",
      "name": "Sanket",
      "matched_entity_id": "person_002",
      "match_confidence": 0.97,
      "operation": "link_existing_entity"
    },
    {
      "type": "project",
      "name": "Agent Memory Migration",
      "matched_entity_id": "project_111",
      "match_confidence": 0.94,
      "operation": "append_context_to_existing_entity"
    },
    {
      "type": "task",
      "name": "Send Sarosh staffing tradeoff note",
      "matched_entity_id": null,
      "match_confidence": null,
      "operation": "create_new_entity"
    }
  ],
  "proposed_changes": [
    {
      "operation": "link_entity",
      "src_id": "note_123",
      "dst_id": "person_001",
      "link_type": "mentions",
      "confidence": 0.97
    },
    {
      "operation": "append_project_note",
      "target_entity_id": "project_111",
      "source_note_id": "note_123",
      "confidence": 0.94
    },
    {
      "operation": "create_task",
      "title": "Send Sarosh staffing tradeoff note",
      "linked_project_id": "project_111",
      "linked_people": ["person_001"],
      "source_note_id": "note_123",
      "confidence": 0.93
    }
  ],
  "suggestions": []
}
```

## 5.3 Supported AI operations

The pipeline must support these operation types:

```text
create_new_entity
update_existing_entity
link_existing_entity
append_context_to_existing_entity
complete_existing_task
reopen_existing_task
change_status
add_follow_up
add_relationship
create_suggestion_for_review
do_nothing
```

## 5.4 Confidence policy

Use this default policy:

|    Confidence | Behavior                             |
| ------------: | ------------------------------------ |
|     `>= 0.92` | Auto-apply if low-risk               |
| `0.70 – 0.91` | Store as suggestion for review       |
|      `< 0.70` | Do not mutate; keep as metadata only |

## 5.5 Auto-apply rules

Auto-apply is allowed for:

```text
Creating task from explicit task language
Linking an existing person mentioned by name
Linking an existing project with strong match
Linking an existing area with strong match
Linking an existing resource by exact URL
Appending non-destructive note/context to existing project/area
Adding derived_from link from created entity to source note
```

## 5.6 Review-required rules

Always require user review for:

```text
Deleting anything
Archiving anything
Merging entities
Changing project status to completed/cancelled
Changing area lifecycle
Completing a task unless match is very explicit
Reopening a task
Creating a new project from ambiguous language
Creating a new area
Creating entities where multiple possible matches exist
Any destructive or irreversible operation
```

## 5.7 Existing entity reconciliation

Before creating any new entity, the AI must search existing entities of the same type.

Matching signals:

```text
Exact title match
Fuzzy title similarity
Semantic similarity
Aliases
Known abbreviations
Entity type
Lifecycle status
Recent activity
Linked people
Linked projects
Linked areas
Resource URL
Person email/name
User correction history
```

Required behavior:

```text
If existing person matches strongly, link existing person.
If existing project matches strongly, update/link existing project.
If existing task matches strongly and capture implies completion, suggest or mark complete based on confidence.
If existing resource has same URL, reuse existing resource.
If multiple possible matches exist, create suggestion, not entity.
If match is weak, do not auto-create duplicate.
```

## 5.8 Duplicate prevention

The AI must avoid obvious duplicates.

Examples of bad behavior:

```text
Creating Person "Sarosh" when Sarosh already exists.
Creating Project "Agent Memory Migration Update" when "Agent Memory Migration" exists.
Creating Resource from same URL multiple times.
Creating Task "Sent feedback to Himmat" instead of completing existing task "Send feedback to Himmat."
```

## 5.9 Source note traceability

Every AI-created or AI-updated entity must link back to the source note/update.

Required links:

```text
Task derived_from Note
Project related/derived_from Note
Area related/derived_from Note
Resource derived_from Note
Person derived_from Note, only if newly created from the note
Note mentions Person, if existing person was referenced
Note references Resource, if resource was cited
```

---

# 6. Capture experience

## 6.1 Primary capture mode

The primary capture UI should be a fast global input.

Placeholder:

```text
Capture anything...
```

The user should be able to submit:

```text
Raw thoughts
Meeting notes
Task dumps
Links
Status updates
Reflections
Project updates
Area updates
Resource saves
People mentions
```

## 6.2 Capture modes

Quick Capture should support these modes:

```text
Auto
Note
Task
Resource
Person
```

Optional later:

```text
Project
Area
```

Default mode:

```text
Auto
```

## 6.3 Mode behavior

| Mode     | Behavior                                            |
| -------- | --------------------------------------------------- |
| Auto     | Save as source note, run AI interpretation          |
| Note     | Save as note, run AI interpretation                 |
| Task     | Create task directly, optionally infer links        |
| Resource | Create resource directly, optionally summarize/link |
| Person   | Create person directly                              |
| Project  | Create project directly, if added later             |
| Area     | Create area directly, if added later                |

## 6.4 Capture should not become a form

Do not require these during capture:

```text
Project
Area
Due date
Tags
Priority
People
Relationship type
Status
```

AI should infer and suggest these after capture.

## 6.5 Post-capture feedback

After capture, show a compact result panel.

Example:

```text
Captured successfully

AI organized this as:
- Updated Project: Agent Memory Migration
- Linked Person: Sarosh
- Linked Person: Sanket
- Created Task: Send Sarosh staffing tradeoff note
- Created Task: Ask Sanket for memory backfill estimate

Needs review:
- Suggested Project: Agent Telemetry Risk Review

Actions:
Undo · Review · Dismiss
```

---

# 7. Review and correction experience

## 7.1 Review queue

The system must include a review queue for AI suggestions and uncertain changes.

Review queue item:

```text
Source note
AI interpretation summary
Proposed changes
Confidence
Accept / edit / dismiss
```

## 7.2 Suggestion actions

The user must be able to:

```text
Accept suggestion
Edit suggestion
Dismiss suggestion
Change target entity
Change operation
Merge with existing entity
Mark AI wrong
Undo recently applied change
```

## 7.3 Correction feedback

Every correction should be recorded as a signal.

Examples:

```text
User changed suggested project target.
User dismissed suggested task.
User merged duplicate person.
User marked AI-created task as wrong.
```

These signals should be stored in `entity_events` or equivalent.

---

# 8. Required UI/UX structure

## 8.1 Primary navigation

Use this navigation structure:

```text
Today
Inbox / Review
Projects
Areas
Tasks
Notes
Resources
People
Search
Archive
```

If screen space is limited, combine Inbox and Review as:

```text
Review
```

## 8.2 Today view

Today is the execution cockpit.

It should show:

```text
Due today
Overdue
Follow-ups
Waiting on people
Suggested next actions
Projects with no next action
Recent captures needing review
```

Do not show vanity metrics.

Avoid:

```text
Total notes
Total resources
Large charts
Random activity streams
Fake productivity scores
```

## 8.3 Inbox / Review view

This view is for processing captured items and AI suggestions.

Sections:

```text
Unprocessed captures
AI suggestions
Ambiguous matches
Potential duplicates
Recently auto-applied changes
Dismissed suggestions, optional
```

Each card should show:

```text
Original captured text
AI summary
Proposed actions
Affected entities
Confidence
Accept / edit / dismiss / undo
```

## 8.4 Projects view

Projects view should show active outcomes.

Each project card should show:

```text
Title
Status
Related area
Next action
Due/follow-up date
Open task count
Waiting/blocker indicator
```

Filters:

```text
Active
Waiting
Blocked
No next action
Completed
Archived
```

## 8.5 Project detail / ProjectFocus

Project detail must emphasize completion and action.

Required sections:

```text
Header
Outcome / description
Status
Related area
Next action
Open tasks
Completed tasks
Linked notes
Linked resources
People involved
Recent updates
Relationships / Linked Context
AI suggestions related to this project
```

Required behavior:

```text
Show "No next action" if active project has no open task.
Allow creating task linked to project.
Allow adding note linked to project.
Allow linking resource.
Allow linking person.
Allow marking project complete.
Completion should trigger wrap-up flow.
```

## 8.6 Areas view

Areas view should show ongoing responsibilities.

Each area card should show:

```text
Title
Standard / purpose summary
Active project count
Recurring/open task count
Recent activity
Needs attention indicator
```

## 8.7 Area detail / AreaFocus

Area detail must emphasize maintenance.

Required sections:

```text
Header
Standard / responsibility statement
Active projects
Maintenance tasks / routines
Recent notes
Resources
People
Needs attention
Linked Context
```

Needs attention signals:

```text
No recent activity
Overdue follow-up
No active project
Open maintenance tasks
Stale linked project
```

Do not use fake health scores unless user explicitly defines measurable standards.

## 8.8 Tasks view

Tasks view should show actionable work.

Filters:

```text
Today
Upcoming
Overdue
Waiting
Blocked
No project
No area
Completed
Archived
```

Task card should show:

```text
Title
Status
Due/follow-up date
Project or area
Person if assigned/involved
Source note indicator if derived
```

## 8.9 Task detail

Required sections:

```text
Title
Status
Due date
Follow-up date
Project / area
Assigned/involved people
Source note if derived
Linked notes
Linked resources
Blocked by / blocks
Activity
```

Actions:

```text
Complete
Reopen
Assign/link person
Move to project
Move to area
Add follow-up
Link resource
View source note
```

## 8.10 Notes view

Notes view should show captured context.

Filters:

```text
Recent
Unprocessed
With suggestions
Meeting notes
Decision notes
Project updates
Area updates
Unlinked
Archived
```

## 8.11 Note detail

Note detail is critical.

Required sections:

```text
Header
Original content/editor
AI interpretation summary
Extracted from this note
Suggestions
Linked Context
Metadata
Activity
```

### Extracted from this note

Show entities created from the note.

Example:

```text
Extracted from this note

Created
- Task: Send staffing tradeoff note
- Task: Ask Sanket for backfill estimate
- Person: Sarosh
- Person: Sanket

Linked Existing
- Project: Agent Memory Migration
- Area: Agent Platform

Suggestions
- Project: Agent Telemetry Risk Review
  Accept · Edit · Dismiss
```

The original note must remain visible and editable.

## 8.12 Resources view

Resources view should show reusable references.

Filters:

```text
Links
Documents
Articles
Internal docs
Unlinked resources
By area
By project
```

Resource card should show:

```text
Title
URL/type
Summary
Linked project/area
Last used/referenced
```

## 8.13 Resource detail

Required sections:

```text
Title
URL/reference
Summary
Why this is useful
Linked projects
Linked areas
Linked notes
Linked tasks
People mentioned/shared by
Create task from resource
Create note from resource
Linked Context
```

## 8.14 People view

People view should show human context, not CRM bloat.

Person card should show:

```text
Name
Open tasks
Waiting-on count
Related projects
Recent note count
```

Do not add unnecessary CRM fields.

Avoid:

```text
Birthdays
Social profiles
Addresses
Relationship scores
Complex contact history
```

## 8.15 Person detail / PersonFocus

Required sections:

```text
Open tasks involving this person
Waiting on this person
Projects involving this person
Notes mentioning this person
Resources shared by / mentioning this person
Areas related to this person
Linked Context
```

This page should answer:

```text
What do I owe this person?
What am I waiting on from this person?
Where are they involved?
What context do I have about them?
```

## 8.16 Search

Search must be global across all entity types.

Search results should be grouped:

```text
Projects
Areas
Tasks
Notes
Resources
People
```

Each result should show:

```text
Entity type
Title
Matched field/snippet
Related context
```

Search should not be note-only.

---

# 9. Shared UI components to build/refactor

## 9.1 Universal entity resolver

Create a frontend helper:

```js
resolveEntity(id, store)
```

It must resolve across:

```text
notes
tasks
projects
areas
resources
people
```

Return:

```js
{
  id,
  type,
  title,
  content,
  status,
  lifecycle,
  route,
  icon
}
```

No UI component should assume a linked entity is a note.

## 9.2 LinkedContextPanel

Build a shared component:

```text
LinkedContextPanel
```

Used by:

```text
NoteDetailView
TaskDetail
ProjectFocus
AreaFocus
PersonFocus
ResourceDetail
```

It should show:

```text
Projects
Areas
Tasks
Notes
Resources
People
Backlinks
```

Each linked item should show:

```text
Icon
Title
Entity type
Relationship label
Source: manual / ai / system
Confidence if available
Remove link action
```

## 9.3 Relationship display mapper

Create a function:

```js
getRelationshipDisplayLabel(srcType, dstType, linkType, direction)
```

Examples:

```text
Task derived_from Note -> Created from note
Note mentions Person -> Mentions
Task parent Project -> Belongs to project
Project parent Area -> Part of area
Note references Resource -> References
Task assigned_to Person -> Assigned to
Task blocks Task -> Blocks
```

Raw `link_type` should not be the primary visible label.

## 9.4 EntityLinkPicker

Create/refactor a component:

```text
EntityLinkPicker
```

Behavior:

```text
Select target entity type
Search target entity
Choose allowed relationship type
Create link
```

It must use relationship allowlist rules.

## 9.5 AISuggestionCard

Reusable card for AI-proposed changes.

Fields:

```text
Source note
Proposed operation
Target entity
Confidence
Reason
Accept
Edit
Dismiss
```

## 9.6 PostCaptureSummary

Shown after capture.

Displays:

```text
Applied changes
Suggestions needing review
Undo action
Review action
```

---

# 10. Backend/API requirements

## 10.1 Universal entity API

Add or normalize these endpoints:

```http
GET    /api/v1/entities/:id
PATCH  /api/v1/entities/:id
DELETE /api/v1/entities/:id
GET    /api/v1/entities/search?q=
GET    /api/v1/entities/:id/links
POST   /api/v1/entities/:id/links
DELETE /api/v1/entities/:id/links/:link_id
GET    /api/v1/entities/:id/delete-preview
```

If equivalent endpoints already exist, use/refactor them instead of duplicating.

## 10.2 Universal links response

`GET /api/v1/entities/:id/links` must return both incoming and outgoing links with enough metadata for UI rendering.

Response shape:

```json
{
  "entity_id": "entity_123",
  "links": [
    {
      "id": "link_001",
      "src_id": "task_123",
      "src_type": "task",
      "src_title": "Send staffing tradeoff note",
      "dst_id": "note_456",
      "dst_type": "note",
      "dst_title": "Meeting with Sarosh",
      "link_type": "derived_from",
      "direction": "outgoing",
      "source": "ai",
      "confidence": 0.94,
      "evidence": "Extracted from note text",
      "created_at": "..."
    }
  ]
}
```

## 10.3 Search API

Add universal search:

```http
GET /api/v1/entities/search?q=
```

Response:

```json
{
  "projects": [],
  "areas": [],
  "tasks": [],
  "notes": [],
  "resources": [],
  "people": []
}
```

## 10.4 Capture API

Add or normalize capture endpoint:

```http
POST /api/v1/capture
```

Request:

```json
{
  "content": "Met Sarosh today...",
  "mode": "auto",
  "source": "quick_capture"
}
```

Response:

```json
{
  "source_note": {},
  "applied_changes": [],
  "suggestions": [],
  "warnings": []
}
```

## 10.5 Suggestions API

Required endpoints:

```http
GET  /api/v1/suggestions
POST /api/v1/suggestions/:id/accept
POST /api/v1/suggestions/:id/dismiss
POST /api/v1/suggestions/:id/edit
```

If suggestions are stored inside `ai_meta`, expose a clean API over them.

Do not force the frontend to manually parse arbitrary `ai_meta` blobs.

## 10.6 Undo API

At minimum, support undo for recent AI-applied change batches.

Recommended:

```http
POST /api/v1/change-batches/:id/undo
```

If full undo is too large for current scope, every post-capture summary must at least link to affected entities and allow manual correction.

---

# 11. Data integrity requirements

## 11.1 No duplicate links

Prevent duplicate links with same:

```text
src_id
dst_id
link_type
```

## 11.2 No self-links

Reject:

```text
src_id == dst_id
```

## 11.3 Parent cardinality

For structural `parent` relationships:

```text
A task should have at most one project parent.
A project should have at most one area parent.
A resource should have at most one primary area parent.
```

Other relationship types may be many-to-many.

## 11.4 Delete preview

Before deleting any entity, show:

```text
Direct links
Backlinks
Entities that may become orphaned
Safe-to-delete linked entities
Entities that must not be deleted automatically
```

Deletion should not cascade silently.

## 11.5 AI change event logging

Every AI or user mutation must create an event.

Events:

```text
entity_created
entity_updated
entity_deleted
link_added
link_removed
ai_interpreted
ai_extracted
ai_suggestion_created
ai_suggestion_accepted
ai_suggestion_dismissed
ai_auto_applied
ai_correction
task_completed
task_reopened
status_changed
```

Each event should include:

```text
actor
source
old_value
new_value
confidence
reason/evidence
created_at
source_note_id where applicable
```

---

# 12. Required refactors

## 12.1 Remove note-only assumptions

Refactor any UI/API/store code that assumes links are only between notes.

Replace note-only link rendering with universal entity rendering.

Bad:

```js
notes.find(n => n.id === linkedId)
```

Good:

```js
resolveEntity(linkedId, store)
```

## 12.2 Replace "Connections" as a model concept

If there are components or labels called `ConnectionsPanel`, either:

```text
Rename to LinkedContextPanel
```

or ensure the component is only a UI wrapper over `entity_links`.

Do not maintain a separate connection state.

## 12.3 Normalize API client

In frontend API client, add:

```js
entitiesAPI
captureAPI
suggestionsAPI
relationshipsAPI
```

Deprecate note-only APIs where they are used for universal behavior.

## 12.4 Normalize store helpers

Add store helpers:

```js
getEntityById(id)
getEntitiesByType(type)
upsertEntity(entity)
removeEntity(id)
getEntityRoute(entity)
getEntityLinks(entityId)
```

Components should use these instead of searching multiple arrays manually.

## 12.5 Refactor QuickCapture

QuickCapture must:

```text
Default to Auto mode
Support explicit modes
Call capture endpoint
Show post-capture summary
Not require metadata fields
```

## 12.6 Refactor NoteDetailView

NoteDetailView must:

```text
Preserve original note
Show AI interpretation
Show extracted entities
Show suggestions
Show linked context
Allow creating task from selection
```

## 12.7 Refactor ProjectFocus

ProjectFocus must become outcome-oriented.

Add:

```text
Outcome section
Next action
No-next-action warning
Open tasks
Linked notes/resources/people
AI suggestions
Linked context
```

## 12.8 Refactor AreaFocus

AreaFocus must become maintenance-oriented.

Add:

```text
Area standard
Active projects
Maintenance/routine tasks
Needs attention
Recent notes
Resources
People
Linked context
```

## 12.9 Refactor PersonFocus

PersonFocus must become context-oriented.

Add:

```text
Open tasks
Waiting on
Related projects
Notes mentioning person
Resources
Areas
Linked context
```

## 12.10 Refactor ResourceDetail

ResourceDetail must show usefulness.

Add:

```text
Summary
Why useful
Linked projects
Linked areas
Linked notes
Linked tasks
People
Create task from resource
Create note from resource
```

---

# 13. Required additions

## 13.1 AI change plan

Implement a structured AI change plan before applying operations.

The change plan should include:

```text
source_note_id
interpretation summary
detected entities
matches to existing entities
proposed operations
confidence
review requirement
applied changes
suggestions
```

## 13.2 Entity reconciliation service

Add a backend service responsible for matching detected entities to existing entities.

Suggested name:

```text
entity_reconciliation_service
```

Responsibilities:

```text
Find existing entity candidates
Score match confidence
Return best match or ambiguous matches
Prevent duplicates
Support entity-type-specific matching
```

Entity-specific matching:

```text
Person: name, alias, email
Resource: URL, title
Project: title, semantic similarity, linked area, active status
Area: title, semantic similarity, active status
Task: title, status, linked project/person, recent activity
Note: semantic similarity only, no auto-merge
```

## 13.3 AI operation applier

Add a service that applies approved operations.

Suggested name:

```text
ai_operation_applier
```

Responsibilities:

```text
Apply safe high-confidence operations
Create suggestions for review-required operations
Create entity events
Create links to source note
Respect data integrity rules
Return applied change batch
```

## 13.4 Suggestions/review model

If no table exists, either:

Option A:

```text
Store suggestions in ai_meta temporarily.
Expose through suggestions API.
```

Option B:

```text
Create ai_suggestions table.
```

Preferred if this is expected to grow:

```text
ai_suggestions
```

Suggested fields:

```text
id
source_entity_id
suggestion_type
operation_type
payload
confidence
reason
status
created_at
updated_at
resolved_at
```

Statuses:

```text
pending
accepted
dismissed
edited
expired
```

## 13.5 Change batch model

If undo/audit is implemented properly, add:

```text
change_batches
```

Suggested fields:

```text
id
source_note_id
actor
source
summary
created_at
undone_at
```

Each entity event can reference a `change_batch_id`.

---

# 14. Required deletions / de-emphasis

## 14.1 Do not build graph visualization as primary UX

If a graph visualization exists, it should not be central.

Prioritize:

```text
Linked context panels
Backlinks
Search
Review queue
Entity detail context
```

Graph views can remain as experimental/debug UI but should not drive the product.

## 14.2 Do not build CRM features

Do not add:

```text
Birthday
Address
Social profile
Relationship strength
Contact timeline
CRM pipeline
```

Unless explicitly requested later.

## 14.3 Do not add new entity types

Do not add:

```text
decision
meeting
goal
routine
event
connection
```

Represent these through existing entities:

```text
Decision -> Note subtype/template
Meeting -> Note subtype/template
Goal -> Project or Area property
Routine -> Task property
Connection -> entity_link
```

## 14.4 Do not build complex dashboards

Avoid:

```text
Vanity metrics
Fake productivity scores
Large charts
Overdesigned home dashboard
```

The system should be calm and action-oriented.

---

# 15. Key user journeys

## 15.1 Capture meeting update

Input:

```text
Met Sarosh today. Sanket moving to Deals could impact memory migration and telemetry. Need to send Sarosh a note and ask Sanket for the backfill estimate.
```

Expected:

```text
Note created and preserved.
Existing Person Sarosh linked.
Existing Person Sanket linked.
Existing Project Agent Memory Migration linked/updated.
Existing Project Agent Telemetry linked/updated.
Task created: Send Sarosh staffing tradeoff note.
Task created: Ask Sanket for backfill estimate.
All created/updated entities linked to source note.
Post-capture summary shown.
```

## 15.2 Capture task completion

Input:

```text
Sent the table feedback to Himmat. Waiting for his response now.
```

Expected:

```text
Find existing task: Send table feedback to Himmat.
Mark complete if confidence is high or suggest completion.
Create/update waiting-on task: Waiting for Himmat response.
Link Himmat.
Link source note.
Show applied changes.
```

## 15.3 Capture resource

Input:

```text
This HealthKit article is useful for workout tracking.
https://example.com/healthkit
```

Expected:

```text
Create or reuse Resource by URL.
Link to relevant project if strongly matched.
Link to Health area if strongly matched.
Create note preserving user context.
Show resource in Resources.
```

## 15.4 Capture area reflection

Input:

```text
Skipped workouts again this week. Sleep has been bad and I'm losing momentum.
```

Expected:

```text
Create note.
Link to Health area.
Suggest task: Restart 3-day workout routine.
Suggest follow-up: Review sleep routine Sunday.
Mark Health area as needs attention through derived signal, not fake score.
```

## 15.5 Direct project management

User opens Project:

```text
Agent Memory Migration
```

They should be able to:

```text
See next action.
See open tasks.
See source notes.
See people involved.
Create task directly.
Add note directly.
Link resource.
Review AI suggestions.
Mark complete.
```

## 15.6 Direct relationship correction

User sees AI linked a note to wrong project.

They should be able to:

```text
Remove wrong relationship.
Link correct project.
Mark correction.
System records feedback.
```

---

# 16. Acceptance criteria

## 16.1 Capture and AI

```text
User can capture unstructured text.
System saves source note.
System interprets captured text.
System detects multiple entities from one note.
System checks existing entities before creating new ones.
System links extracted entities to source note.
System auto-applies safe high-confidence changes.
System stores uncertain changes as suggestions.
System shows post-capture summary.
```

## 16.2 Notes

```text
Original note remains visible.
Original note remains editable.
Note is not silently converted.
Note shows extracted entities.
Note shows suggestions.
Note shows linked context.
```

## 16.3 Entity reconciliation

```text
Existing people are reused.
Existing projects are reused.
Existing resources are reused by URL.
Existing tasks can be completed/updated rather than duplicated.
Ambiguous matches become suggestions.
Duplicates are minimized.
```

## 16.4 Relationships

```text
All relationships use entity_links.
No separate connection model exists.
LinkedContextPanel works across all entity types.
Incoming and outgoing links are shown.
Relationship labels are human-readable.
Links route to correct entity detail pages.
```

## 16.5 UI

```text
Today shows actionable work.
Review shows AI suggestions and uncertain changes.
Project detail is outcome-oriented.
Area detail is maintenance-oriented.
Person detail is context-oriented.
Resource detail shows usefulness.
Search works across all entity types.
```

## 16.6 Safety/control

```text
User can accept suggestions.
User can dismiss suggestions.
User can edit suggestions.
User can undo or manually correct AI-applied changes.
Destructive changes require review.
Merges require review.
Deletes require preview.
```

---

# 17. Testing requirements

## 17.1 Backend tests

Add tests for:

```text
Note remains note after extraction.
One note can generate multiple tasks.
One note can link multiple people.
Existing person is reused.
Existing project is reused.
Existing resource is reused by URL.
Existing task can be completed based on capture.
Ambiguous match creates suggestion.
Low-confidence match does not mutate data.
Created task links back to source note with derived_from.
Universal links endpoint returns incoming and outgoing links.
Duplicate links are rejected.
Self-links are rejected.
Delete preview works.
AI events are logged.
```

## 17.2 Frontend tests

Add tests for:

```text
QuickCapture Auto mode saves capture.
QuickCapture Task mode creates task directly.
PostCaptureSummary renders applied changes.
PostCaptureSummary renders suggestions.
NoteDetailView shows extracted entities.
LinkedContextPanel renders all entity types.
resolveEntity resolves note/task/project/area/resource/person.
Relationship labels are human-readable.
AISuggestionCard supports accept/edit/dismiss.
ProjectFocus shows no-next-action warning.
AreaFocus shows needs-attention section.
PersonFocus shows waiting-on tasks.
ResourceDetail shows linked projects/areas/tasks/notes.
```

## 17.3 Integration tests

Add end-to-end test:

```text
Capture note mentioning two people, two projects, and two tasks.
Verify source note exists.
Verify existing people/projects are reused.
Verify tasks are created.
Verify all links exist.
Verify note detail shows extracted entities.
Verify project detail shows linked note/tasks.
Verify person detail shows related tasks/notes.
```

Add second end-to-end test:

```text
Create task "Send feedback to Himmat."
Capture "Sent feedback to Himmat. Waiting for response."
Verify original task is completed or completion suggestion appears.
Verify waiting-on task exists or is suggested.
Verify Himmat is linked.
```

---

# 18. Implementation phases

## Phase 1: Foundation cleanup

Scope:

```text
Universal entity resolver
Universal links API usage
LinkedContextPanel
Relationship display mapper
Remove note-only link assumptions
Ensure entity_links is the only relationship model
```

Done when:

```text
Every entity detail page can show relationships to every other entity type.
No component assumes links are note-only.
```

## Phase 2: Capture and AI change plan

Scope:

```text
Capture endpoint
Source note preservation
Structured AI interpretation output
Entity reconciliation service
AI change plan generation
Confidence policy
```

Done when:

```text
A captured update produces a source note and structured proposed/applied changes.
Existing entities are checked before creation.
```

## Phase 3: AI operation applier and suggestions

Scope:

```text
Apply high-confidence changes
Create suggestions for uncertain changes
Record entity events
Link changes to source note
Suggestions API
Review UI
```

Done when:

```text
AI can safely maintain the system with reviewable suggestions.
```

## Phase 4: Quick Capture UX

Scope:

```text
Auto / Note / Task / Resource / Person modes
Post-capture summary
Undo/manual correction entry points
```

Done when:

```text
User can capture naturally and immediately see how the system organized it.
```

## Phase 5: Entity detail UX

Scope:

```text
NoteDetail extracted entities
ProjectFocus outcome/next action
AreaFocus maintenance/needs attention
PersonFocus open loops
ResourceDetail usefulness
TaskDetail source/context
```

Done when:

```text
The UI supports sensemaking and direct management across all entities.
```

## Phase 6: Today, Review, Search

Scope:

```text
Today execution cockpit
Review queue
Global entity search
Projects with no next action
Waiting-on people
Unprocessed captures
```

Done when:

```text
The system feels like a productivity operating system rather than CRUD pages.
```

---

# 19. Files/areas to inspect before implementation

The agent should inspect these before making changes:

```text
models.py
docs/SCHEMA.sql
docs/PRD.md
docs/TECH_SPEC.md

services/ai_pipeline.py
services/link_service.py
services/entity_service.py
services/*classification*
services/*embedding*
services/*ingest*

api/*routes*
api/*entities*
api/*notes*
api/*links*
api/*capture*

ui/src/api/engram.js
ui/src/stores/useStore.js

ui/src/components/capture/QuickCapture.jsx
ui/src/components/ConnectionsPanel/*
ui/src/components/LinkToEntity/*
ui/src/components/*Suggestion*
ui/src/components/*Entity*

ui/src/views/Today.jsx
ui/src/views/Inbox.jsx
ui/src/views/Review.jsx
ui/src/views/NoteDetailView.jsx
ui/src/views/ProjectFocus.jsx
ui/src/views/AreaFocus.jsx
ui/src/views/PersonFocus.jsx
ui/src/views/ResourceDetail.jsx
ui/src/views/Tasks.jsx
ui/src/views/Search.jsx
```

---

# 20. Agent implementation instructions

The development agent must follow these rules:

```text
Do not introduce new primary entity types.
Do not create a separate connections model.
Do not delete or replace existing notes during AI extraction.
Do not create entities before checking existing ones.
Do not auto-apply destructive changes.
Do not build graph visualization as the main UX.
Do not add CRM bloat.
Do not create duplicate APIs if equivalent APIs already exist.
Prefer refactoring existing services over adding parallel systems.
Add tests for every behavior change.
Keep UI minimal, calm, and action-oriented.
```

The development agent should produce:

```text
Implementation plan
List of files to modify
Backend changes
Frontend changes
Migration changes if any
Tests added
Manual QA checklist
Known limitations
```

---

# 21. Manual QA checklist

After implementation, manually verify:

```text
Capture creates source note.
Capture can create multiple linked tasks.
Capture links existing people instead of duplicating.
Capture links existing projects instead of duplicating.
Capture reuses resource by URL.
Note remains note.
Note detail shows extracted entities.
Project detail shows linked notes/tasks/resources/people.
Area detail shows active projects and maintenance tasks.
Person detail shows open loops and waiting-on items.
Resource detail shows linked context.
Today shows due/follow-up/waiting/no-next-action sections.
Review queue shows suggestions.
User can accept suggestion.
User can dismiss suggestion.
User can edit suggestion.
User can remove wrong relationship.
Search finds all entity types.
Delete preview prevents accidental cascade.
```

---

# 22. Definition of done

This work is done when Engram supports this complete loop:

```text
User captures a natural-language update.
Engram saves the original note.
AI interprets the update.
AI checks existing entities first.
AI updates, links, completes, or creates entities as appropriate.
AI avoids duplicate creation.
All changes are linked back to the source note.
User sees what happened.
User can review, correct, undo, or directly manage the system.
Today, Projects, Areas, Tasks, Notes, Resources, and People all reflect the updated system state.
```

---

# 23. One-line summary for the agent

```text
Build Engram into an AI-maintained productivity operating system: natural-language capture creates a preserved source note, AI reconciles against existing projects/areas/tasks/notes/resources/people before applying changes, all changes are linked through entity_links, and the UI acts as a calm control room for review, correction, search, and direct management.
```
