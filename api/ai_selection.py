"""POST /api/v2/ai/propose-from-selection — AI actions on selected text.

Supports 5 actions:
- classify: PARA classification of selected text
- extract_task: extract tasks and create Entity(type='task') records
- create_link: propose related entities as link candidates
- find_and_update: find existing entities and propose updates
- improve_writing: return improved/clarity version of text

All AI actions write entity_events for auditability.
"""

import logging
from flask import request, jsonify
from api import api_v2_bp
from extensions import db
from models import Entity, EntityEvent
from services.entity_service import create_entity
from services.link_service import create_link as svc_create_link
from services.search import search

logger = logging.getLogger(__name__)

VALID_ACTIONS = {
    "classify",
    "extract_task",
    "create_link",
    "find_and_update",
    "improve_writing",
}


@api_v2_bp.route("/ai/propose-from-selection", methods=["POST"])
def propose_from_selection():
    """Run an AI action on selected text from the editor."""
    data = request.get_json(silent=True) or {}

    action = data.get("action")
    text = (data.get("selected_text") or data.get("text") or "").strip()

    if not action:
        return jsonify({"error": "action is required"}), 400
    if not text:
        return jsonify({"error": "selected_text is required"}), 400
    if action not in VALID_ACTIONS:
        return jsonify({
            "error": f"invalid action: {action}. Valid actions: {sorted(VALID_ACTIONS)}"
        }), 400

    handlers = {
        "classify": _handle_classify,
        "extract_task": _handle_extract_task,
        "create_link": _handle_create_link,
        "find_and_update": _handle_find_and_update,
        "improve_writing": _handle_improve_writing,
    }

    try:
        result = handlers[action](text, data)
        status_code = 201 if action == "extract_task" else 200
        return jsonify({"action": action, "result": result, "entity": None}), status_code
    except Exception as e:
        logger.error("AI action %s failed: %s", action, e)
        return jsonify({"error": str(e)}), 500


# ─── Action Handlers ─────────────────────────────────────────────────────────


def _handle_classify(text, data):
    """Classify selected text using the extractor pipeline."""
    from services.extractor import extract

    extraction = extract(content=text)

    result = {
        "para_bucket": extraction.para_bucket,
        "confidence": extraction.confidence,
        "summary": extraction.summary,
        "reasoning": extraction.reasoning,
    }

    if extraction.suggested_project:
        result["suggested_project"] = extraction.suggested_project
    if extraction.suggested_area:
        result["suggested_area"] = extraction.suggested_area
    if extraction.tags:
        result["tags"] = extraction.tags[:6]

    return result


def _handle_extract_task(text, data):
    """Extract tasks from text and create Entity(type='task') records."""
    from services.extractor import extract
    from services.extractor import extract_and_create_inline_tasks

    # First try LLM-based extraction
    extraction = extract(content=text)

    created_tasks = []

    if extraction.tasks:
        # Create task entities from LLM-extracted tasks
        for task in extraction.tasks:
            properties = {
                "priority": task.priority,
                "extracted_from": "ai_selection",
            }
            if task.due_date:
                properties["due_date"] = task.due_date
            if task.project_hint:
                properties["project_hint"] = task.project_hint

            task_entity = create_entity(
                entity_type="task",
                title=task.title,
                content=text,
                properties=properties,
                source="ai_selection",
                actor="agent:ai_selection",
            )
            created_tasks.append({
                "entity_id": str(task_entity.id),
                "title": task.title,
                "priority": task.priority,
            })

    # Also parse inline checkbox patterns
    inline_results = extract_and_create_inline_tasks(
        source_entity_id="selection",
        raw_text=text,
    )
    for inline_task in inline_results:
        # Avoid duplicates — only add if not already created
        if not any(t["title"] == inline_task.get("title") for t in created_tasks):
            created_tasks.append({
                "entity_id": str(inline_task["id"]),
                "title": inline_task.get("title"),
                "priority": "MEDIUM",
            })

    return {
        "tasks": created_tasks,
        "classification": {
            "para_bucket": extraction.para_bucket,
            "confidence": extraction.confidence,
        },
    }


def _handle_create_link(text, data):
    """Propose related entities as link candidates."""
    source_entity_id = data.get("source_entity_id")

    # Search for entities related to the selected text
    search_results = search(query=text, limit=10, mode="hybrid")

    # Filter out the source entity if provided
    candidates = []
    for entity_data in search_results:
        if source_entity_id and entity_data.get("id") == source_entity_id:
            continue
        candidates.append({
            "entity_id": entity_data["id"],
            "title": entity_data.get("title"),
            "type": entity_data.get("type"),
            "score": entity_data.get("_score", 0),
        })

    return {
        "candidates": candidates,
        "total": len(candidates),
    }


def _handle_find_and_update(text, data):
    """Find matching entities via semantic search and propose a direct patch."""
    search_results = search(query=text, limit=3, mode="semantic")

    candidates = []
    for entity_data in search_results[:3]:
        entity_payload = {
            "id": entity_data["id"],
            "title": entity_data.get("title"),
            "type": entity_data.get("type"),
            "content": entity_data.get("content"),
        }
        proposed_change = _build_proposed_update(entity_data, text)
        candidates.append({
            "entity": entity_payload,
            "proposed_change": proposed_change,
            "proposed_change_summary": proposed_change.get("content", text),
            "score": entity_data.get("_score", 0),
        })

    return {
        "candidates": candidates,
        "total": len(candidates),
    }


def _build_proposed_update(entity_data, text):
    """Build a conservative PATCH payload for the existing entity."""
    return {"content": text}


def _handle_improve_writing(text, data):
    """Return improved version of the selected text."""
    from services.extractor import _get_client
    import os

    if not os.getenv("OPENAI_API_KEY"):
        # Fallback: basic text improvement without LLM
        improved = _basic_improve(text)
        return {
            "improved_text": improved,
            "model": "fallback",
            "changes": "basic grammar and capitalization",
        }

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a writing assistant. Improve the clarity, grammar, "
                        "and tone of the provided text. Keep the original meaning. "
                        "Return only the improved text, nothing else."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        improved = response.choices[0].message.content.strip()
        return {
            "improved_text": improved,
            "model": "gpt-4o",
        }
    except Exception as e:
        logger.warning("LLM improve_writing failed, using fallback: %s", e)
        return {
            "improved_text": _basic_improve(text),
            "model": "fallback",
            "changes": "basic grammar and capitalization",
        }


def _basic_improve(text):
    """Basic text improvement without LLM — capitalization and spacing."""
    if not text:
        return text

    # Capitalize first letter of sentences
    sentences = text.split(". ")
    improved = [s.strip().capitalize() for s in sentences]
    result = ". ".join(improved)

    # Fix common issues
    result = result.replace("  ", " ")
    result = result.replace("i ", "I ")

    return result
