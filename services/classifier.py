import os
import time
import logging
from openai import OpenAI
from openai import RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PARA_BUCKETS = ["inbox", "projects", "areas", "resources", "archives"]

CLASSIFIER_PROMPT = """You are an assistant that classifies notes using the PARA method:
- Projects: active work with a deadline or outcome you're working toward
- Areas: ongoing responsibilities you maintain (no end date)
- Resources: reference material worth keeping for later
- Archives: dormant information保留 but potentially useful
- Inbox: needs processing or isn't clear yet

Classify this note. Respond ONLY with valid JSON:
{{
  "bucket": "inbox|projects|areas|resources|archives",
  "suggested_project": "project name or null",
  "suggested_area": "area name or null",
  "suggested_tags": ["tag1", "tag2"],
  "reasoning": "one sentence why"
}}

Note to classify:
---
{raw_text}
---"""


def classify_note(raw_text: str) -> dict:
    """
    Classify a raw note into PARA bucket using OpenAI GPT-4o.
    Returns dict with bucket, suggested_project, suggested_area, suggested_tags, reasoning.
    On failure, returns bucket='inbox' and logs the error.
    """
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not set — skipping classification")
        return {
            "bucket": "inbox",
            "suggested_project": None,
            "suggested_area": None,
            "suggested_tags": [],
            "reasoning": "no API key",
            "confidence": 0.0,
        }

    # Build project/area context from existing DB for better suggestions
    # (passed in by caller for now, keep simple)

    prompt = CLASSIFIER_PROMPT.format(raw_text=raw_text)

    # Exponential backoff for rate limits
    max_attempts = 4
    last_error = None

    for attempt in range(max_attempts):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a PARA classification assistant. Always respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=300,
            )

            content = response.choices[0].message.content
            import json

            result = json.loads(content)
            result["confidence"] = 0.8  # placeholder until we parse usage

            # Validate bucket
            if result.get("bucket") not in PARA_BUCKETS:
                result["bucket"] = "inbox"

            return result

        except RateLimitError as e:
            wait_time = (2**attempt) * 1.0
            logger.warning(f"OpenAI rate limit, retrying in {wait_time}s: {e}")
            time.sleep(wait_time)
            last_error = e

        except APITimeoutError as e:
            wait_time = (2**attempt) * 1.0
            logger.warning(f"OpenAI timeout, retrying in {wait_time}s: {e}")
            time.sleep(wait_time)
            last_error = e

        except Exception as e:
            logger.error(f"Classification error: {e}")
            last_error = e
            break

    # All retries failed
    logger.error(f"Classification failed after {max_attempts} attempts: {last_error}")
    return {
        "bucket": "inbox",
        "suggested_project": None,
        "suggested_area": None,
        "suggested_tags": [],
        "reasoning": f"classification failed: {last_error}",
        "confidence": 0.0,
    }
