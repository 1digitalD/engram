#!/usr/bin/env python3
"""Generate exec-spec slice docs in docs/iterations/ from PRDs.

Follows the existing ITERATION_*.md pattern in the engram repo.
"""
import json
from pathlib import Path

REPO = Path("/Volumes/lex1t/dev/shared/repos/engram")
OUT_DIR = REPO / "docs/iterations"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PRDS = [
    (1, REPO / "prd-phase1.json"),
    (2, REPO / "prd-phase2.json"),
    (3, REPO / "prd-phase3.json"),
    (4, REPO / "prd-phase4.json"),
]


TEMPLATE = """# SLICE_{phase}_{num} — {title}

> **Phase {phase} / {iteration}**
> **Task id:** `{task_id}`
> **Risk:** {risk}
> **Status:** Pending (Loopsmith will set `passes: true` on success)

## Goal

{description}

## Acceptance criteria

{criteria}

## Validation commands

These run from the main repo path (worktrees do not carry gitignored `venv/`
or `node_modules/`):

```
{validations}
```

## Files affected

{files}

## Slice doc references

- **Design intent** (workspace): `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/_slices/SLICE_{phase}_{num}_{slug}.md`
- **Design brief**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/02-fresh-pass.md`
- **Discussion archive**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/03-discussion-archive.md`
- **Execution tracker**: `/Volumes/lex1t/OC-workspace/projects/engram-ux-redesign/04-execution-tracker.md`
- **PRD task**: `prd{phase_suffix}.json` → `tasks[{task_index}]`

## Results (filled in by Loopsmith on completion)

<!-- Loopsmith agent: fill in below. Replace each placeholder with actual evidence.
     Required: test output (last 10-20 lines), commit SHA, replay metrics diff (if AI-touching).
-->

**Commit:** `<sha>`

**Tests:**
```
<paste test output>
```

**Replay metrics (if applicable):**
```
<paste replay_eval.py output>
```

**Manual smoke:**
<describe what you tested, what passed, what didn't>

**Notes / follow-ups:**
<any caveats, follow-up slices, or things the next slice should know>

**Acceptance met:** [ ] yes / [ ] no (if no, document what's missing)
"""


def main():
    written = 0
    for phase_num, prd_path in PRDS:
        if not prd_path.exists():
            print(f"SKIP: {prd_path} not found")
            continue
        with open(prd_path) as f:
            prd = json.load(f)

        iteration = prd.get("iteration", "unknown")

        for task_index, task in enumerate(prd["tasks"]):
            task_id = task["id"]
            title = task["title"]
            num = task_index + 1
            slug = task_id.replace("prd-", "")

            criteria = "\n".join(f"- {c}" for c in task["acceptanceCriteria"])
            validations = "\n".join(f"  {v}" for v in task["validationCommands"])

            files = ", ".join(prd.get("scope", {}).get("filesAffected", []))
            if not files:
                files = "(see PRD scope)"

            phase_suffix = "" if phase_num == 1 else f"-phase{phase_num}"

            content = TEMPLATE.format(
                phase=phase_num,
                num=num,
                title=title,
                task_id=task_id,
                iteration=iteration,
                risk=task.get("risk", "low"),
                description=task.get("description", ""),
                criteria=criteria,
                validations=validations,
                files=files,
                slug=slug,
                phase_suffix=phase_suffix,
                task_index=task_index,
            )

            out_path = OUT_DIR / f"SLICE_{phase_num}_{num}_{slug}.md"
            out_path.write_text(content)
            written += 1
            print(f"Wrote {out_path}")

    print(f"\nTotal: {written} slice docs")


if __name__ == "__main__":
    main()
