"""Entity-sized semantic documents with exact source facts and memberships."""

from resourcing_assistant.agent.schemas import Candidate


class SourceDocuments:
    def __init__(self, source):
        self.source = source

    def candidates(self, kind, eligible=None):
        result = []
        key = {"person": "person_id", "project": "engagement_id", "risk": "risk_id"}[
            kind
        ]
        for facts in self.source.document_facts(kind, eligible):
            if kind == "person":
                text = "\n".join(
                    [
                        facts["bio"] or "",
                        "Roles: " + ", ".join(facts["roles"]),
                        "Skills: " + ", ".join(s["name"] for s in facts["skills"]),
                    ]
                )
            elif kind == "project":
                text = "\n".join(
                    [facts["summary"] or ""]
                    + [r["description"] or "" for r in facts["risks"]]
                )
            else:
                text = facts["description"] or ""
            result.append(
                Candidate(
                    source_id=f"{kind}:{facts[key]}",
                    kind=kind,
                    entity_id=facts[key],
                    text=text,
                    facts=facts,
                )
            )
        return result
