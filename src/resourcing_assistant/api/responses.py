"""Build public answer blocks from verified source data."""


def card(action):
    return {
        "type": "confirmation",
        "action_id": action["action_id"],
        "status": action["status"],
        "fields": action["fields"],
        "booking_id": action["booking_id"],
    }


def text_block(text):
    return {"type": "text", "text": text}


def table_block(result):
    return {
        "type": "table",
        "block_id": result["query_id"],
        "title": result["purpose"],
        "columns": [
            {"key": key, "label": key.replace("_", " ")} for key in result["columns"]
        ],
        "rows": result["rows"],
        "completeness": {
            "mode": "structured",
            "truncated": result["truncated"],
            "has_more": result["truncated"],
        },
        "evidence": [
            {"query_id": result["query_id"], "source_tables": result["source_tables"]}
        ],
    }
