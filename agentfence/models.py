"""Strict public contracts. Caller identity is never accepted in a proposal."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Proposal(StrictModel):
    task_id: Identifier
    tool: Identifier
    arguments: dict
    user_input: str = Field(default="", max_length=4000)
    retrieved_context: str = Field(default="", max_length=8000)
    prior_tool_output: str = Field(default="", max_length=8000)


class Scoped(StrictModel):
    tenant_id: Identifier
    case_id: Identifier


class AssetArgs(Scoped):
    asset_id: Identifier


class SearchArgs(Scoped):
    query: str = Field(min_length=1, max_length=160)
    limit: int = Field(default=3, ge=1, le=5)


class DocumentArgs(Scoped):
    document_id: Identifier


class DisableArgs(Scoped):
    key_id: Identifier
    reason: Literal["suspected_compromise", "incident_containment"]


class ExportArgs(AssetArgs):
    destination: str = Field(min_length=1, max_length=200)


class Review(StrictModel):
    approve: bool
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


SCHEMAS = {
    "get_asset_metadata": AssetArgs,
    "search_incident_runbooks": SearchArgs,
    "read_document": DocumentArgs,
    "disable_access_key": DisableArgs,
    "export_asset_report": ExportArgs,
}
