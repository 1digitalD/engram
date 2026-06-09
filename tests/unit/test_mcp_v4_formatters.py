from mcp_server.v4_formatters import format_entity, format_recent, format_search_results


def test_format_search_results_uses_v4_payload():
    text = format_search_results(
        {
            "results": [{
                "entity": {"id": "p1", "type": "project", "title": "Memory Lookup"},
                "score": 0.91,
                "match": {"source": "keyword", "snippet": "rollout"},
            }]
        },
        "memory",
    )

    assert "Memory Lookup" in text
    assert "score=0.910" in text
    assert "source=keyword" in text
    assert "rollout" in text


def test_format_entity_includes_relationship_sections():
    text = format_entity(
        {
            "entity": {"id": "t1", "type": "task", "title": "Follow up", "status": "open", "lifecycle": "active"},
            "sections": [{
                "title": "Project",
                "items": [{
                    "entity": {"id": "p1", "title": "Memory Lookup"},
                    "relationship": {"relationship_type": "parent"},
                }],
            }],
        }
    )

    assert "Task `t1`" in text
    assert "Relationships:" in text
    assert "Memory Lookup" in text
    assert "parent" in text


def test_format_recent_lists_entities():
    text = format_recent({"data": [{"id": "n1", "type": "note", "title": "Captured note"}]}, entity_type="note")

    assert "Recent note entities" in text
    assert "Captured note" in text
