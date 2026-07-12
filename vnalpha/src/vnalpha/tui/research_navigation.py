from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group, RenderableType
from rich.text import Text

from vnalpha.commands.models import CommandResult


@dataclass(frozen=True, slots=True)
class ArtifactDetailState:
    artifact_id: str
    command: str
    title: str
    subject: str
    result: CommandResult
    note_command: str | None
    assistant_prompt: str


def build_artifact_states(
    command: str,
    result: CommandResult,
) -> tuple[ArtifactDetailState, ...]:
    metadata = result.metadata if isinstance(result.metadata, dict) else {}
    subject = str(metadata.get("subject") or "").strip().upper()
    title = str(metadata.get("artifact_id") or result.title)
    states: list[ArtifactDetailState] = []
    for artifact in result.artifacts:
        artifact_id = artifact.name
        states.append(
            ArtifactDetailState(
                artifact_id=artifact_id,
                command=command,
                title=title,
                subject=subject,
                result=result,
                note_command=_note_command(subject, artifact_id, result.summary),
                assistant_prompt=_assistant_prompt(subject, artifact_id),
            )
        )
    return tuple(states)


def artifact_detail_renderable(state: ArtifactDetailState) -> RenderableType:
    from vnalpha.commands.renderers.textual_renderer import result_to_markup

    return Group(
        Text("Artifact detail", style="bold cyan"),
        Text(
            "Ctrl+B back  Ctrl+Y artifact id  Ctrl+S note  Ctrl+R assistant",
            style="dim",
        ),
        result_to_markup(state.result),
    )


def _assistant_prompt(subject: str, artifact_id: str) -> str:
    focus = subject or artifact_id
    return (
        f"Review research artifact {artifact_id} for {focus}. "
        "Summarize caveats, missing data, and next monitoring steps."
    )


def _note_command(
    subject: str,
    artifact_id: str,
    summary: str | None,
) -> str | None:
    if not subject:
        return None
    note_body = summary or f"Review {artifact_id}"
    safe_body = note_body.replace('"', "'")
    return f'/note {subject} "{safe_body} [{artifact_id}]"'
