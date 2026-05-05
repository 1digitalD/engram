import os
import time
import logging
from openai import OpenAI, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)

_client = None

def _get_client():
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = OpenAI(api_key=key)
    return _client

PARA_BUCKETS = ["INBOX", "PROJECTS", "AREAS", "RESOURCES", "ARCHIVES"]

CLASSIFIER_PROMPT = """You are an assistant that classifies notes using the PARA method:
- PROJECTS: active work with a deadline or outcome you're working toward
- AREAS: ongoing responsibilities you maintain (no end date)
- RESOURCES: reference material worth keeping for later
- ARCHIVES: dormant information but potentially useful
- INBOX: needs processing or isn't clear yet

Classify this note. Respond ONLY with valid JSON:
{{
  "bucket": "INBOX|PROJECTS|AREAS|RESOURCES|ARCHIVES",
  "suggested_project": "project name or null",
  "suggested_area": "area name or null",
  "suggested_tags": ["tag1", "tag2"],
  "reasoning": "one sentence why",
  "confidence": 0.0
}}

The confidence field (0.0-1.0) should reflect how certain you are about the classification:
- 0.9+ : very clear classification
- 0.7-0.9: reasonably confident
- 0.5-0.7: uncertain, multiple buckets could fit
- below 0.5: very unclear, use INBOX

Note to classify:
---
{raw_text}
---

Existing projects (prefer matching these by name if relevant): {projects}
Existing areas (prefer matching these by name if relevant): {areas}
"""


def classify_note(raw_text: str, projects: list = None, areas: list = None) -> dict:
    """
    Classify a raw note into PARA bucket using OpenAI GPT-4o.
    Returns dict with bucket, suggested_project, suggested_area, suggested_tags, reasoning, confidence.
    On failure, returns bucket='INBOX' and logs the error.
    """
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not set — skipping classification")
        return {
            "bucket": "INBOX",
            "suggested_project": None,
            "suggested_area": None,
            "suggested_tags": [],
            "reasoning": "no API key",
            "confidence": 0.0,
        }

    projects_str = ", ".join(projects) if projects else "(none)"
    areas_str = ", ".join(areas) if areas else "(none)"

    prompt = CLASSIFIER_PROMPT.format(
        raw_text=raw_text,
        projects=projects_str,
        areas=areas_str,
    )

    max_attempts = 4
    last_error = None

    for attempt in range(max_attempts):
        try:
            response = _get_client().chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a PARA classification assistant. Always respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=300,
            )

            import json
            content = response.choices[0].message.content
            result = json.loads(content)

            # Normalize bucket to uppercase
            bucket = result.get("bucket", "INBOX").upper()
            if bucket not in PARA_BUCKETS:
                bucket = "INBOX"
            result["bucket"] = bucket

            # Clamp confidence
            confidence = float(result.get("confidence", 0.7))
            result["confidence"] = max(0.0, min(1.0, confidence))

            return result

        except RateLimitError as e:
            wait_time = (2 ** attempt) * 1.0
            logger.warning(f"OpenAI rate limit, retrying in {wait_time}s: {e}")
            time.sleep(wait_time)
            last_error = e

        except APITimeoutError as e:
            wait_time = (2 ** attempt) * 1.0
            logger.warning(f"OpenAI timeout, retrying in {wait_time}s: {e}")
            time.sleep(wait_time)
            last_error = e

        except Exception as e:
            logger.error(f"Classification error: {e}")
            last_error = e
            break

    logger.error(f"Classification failed after {max_attempts} attempts: {last_error}")
    return {
        "bucket": "INBOX",
        "suggested_project": None,
        "suggested_area": None,
        "suggested_tags": [],
        "reasoning": f"classification failed: {last_error}",
        "confidence": 0.0,
    }
