from __future__ import annotations

from typing import TYPE_CHECKING

from rich.markup import escape as escape_markup
from rich.text import Text

from vnalpha.tui.models.conversation import (
    ActivityMessage,
    ApprovalRequestMessage,
    AssistantAnswerMessage,
    CommandResultMessage,
    ErrorMessage,
    UserMessage,
    WarningMessage,
)

if TYPE_CHECKING:
    from vnalpha.commands.executor import TraceEvent
    from vnalpha.commands.models import CommandResult
    from vnalpha.tui.models.conversation import ConversationMessage
    from vnalpha.tui.research_navigation import ArtifactDetailState

try:
    from rich.console import RenderableType
    from textual.app import ComposeResult
    from textual.widget import Widget
    from textual.widgets import RichLog

    _TEXTUAL_AVAILABLE = True
except ImportError:
    RenderableType = object  # type: ignore[assignment,misc]
    _TEXTUAL_AVAILABLE = False


if _TEXTUAL_AVAILABLE:

    class OutputStream(Widget):
        DEFAULT_CSS = """
        OutputStream {
            height: 1fr;
            border: round $surface-darken-1;
        }
        OutputStream > RichLog {
            height: 1fr;
            scrollbar-gutter: stable;
        }
        """

        def __init__(self, *, max_messages: int = 300, **kwargs) -> None:
            super().__init__(**kwargs)
            self._max_messages = max(50, max_messages)
            self._messages: list[ConversationMessage] = []
            self._latest_artifact_states: tuple[ArtifactDetailState, ...] = ()
            self._artifact_stack: list[ArtifactDetailState] = []
            self._artifact_snapshot_stack: list[tuple[str, ...]] = []
            self._detail_mode = False

        def compose(self) -> ComposeResult:
            yield RichLog(id="output-log", markup=False, wrap=True, highlight=False)

        def on_mount(self) -> None:
            try:
                self.query_one("#output-log", RichLog).can_focus = False
            except Exception:
                pass

        def append_message(self, message: "ConversationMessage") -> None:
            self._messages.append(message)
            if len(self._messages) > self._max_messages:
                self._messages = self._messages[-self._max_messages :]
            if self._detail_mode:
                self._detail_mode = False
                self.clear_visible()
                self._rerender_messages()
            self._render_typed_message(message)

        def show_user_input(self, text: str, *, prompt_type: str = "natural") -> None:
            self.append_message(UserMessage(text=text, prompt_type=prompt_type))

        def page_up(self, count: int = 3) -> None:
            self._scroll_log("scroll_up", count)

        def page_down(self, count: int = 3) -> None:
            self._scroll_log("scroll_down", count)

        def home(self) -> None:
            self._scroll_to_boundary("scroll_home")

        def end(self) -> None:
            self._scroll_to_boundary("scroll_end")

        def show_assistant_message(self, text: str, style: str | None = None) -> None:
            self._write(self._safe_text(text, style=style))

        def show_command_result(self, command: str, result: "RenderableType") -> None:
            self._write(self._safe_text(f"$ {command}", style="bold"))
            self._append_command_result(result)

        def show_error(self, message: str, source: str | None = None) -> None:
            source_part = f" ({source})" if source else ""
            self.append_message(ErrorMessage(text=f"Error{source_part}: {message}"))

        def show_warning(self, message: str, source: str | None = None) -> None:
            source_part = f" ({source})" if source else ""
            self.append_message(WarningMessage(text=f"Warning{source_part}: {message}"))

        def show_trace_event(self, event: "TraceEvent") -> None:
            if event.status == "RUNNING":
                self.append_message(
                    ActivityMessage(f"tool: {event.tool_name}", detail="running")
                )
            elif event.status == "SUCCESS":
                ms = (
                    f" ({event.duration_ms:.0f}ms)"
                    if event.duration_ms is not None
                    else ""
                )
                self.append_message(
                    ActivityMessage(f"tool: {event.tool_name}{ms}", detail="done")
                )
            else:
                ms = (
                    f" ({event.duration_ms:.0f}ms)"
                    if event.duration_ms is not None
                    else ""
                )
                self.append_message(ErrorMessage(f"tool: {event.tool_name}{ms} failed"))

        def show_data_ensure_progress(
            self,
            step: str,
            status: str,
            detail: str = "",
        ) -> None:
            if status == "running":
                self.append_message(ActivityMessage(f"{step}", detail="running"))
            elif status == "done":
                suffix = f" — {detail}" if detail else ""
                self.append_message(ActivityMessage(f"{step}{suffix}", detail="done"))
            else:
                suffix = f" — {detail}" if detail else ""
                self.append_message(ErrorMessage(f"{step}{suffix}"))

        def show_table_or_markup(self, markup: "RenderableType") -> None:
            self._write(markup)

        def show_repair_bundle(self, path: str, repair_id: str | None = None) -> None:
            rid = f" [{repair_id}]" if repair_id else ""
            self.append_message(
                CommandResultMessage("repair", f"Repair bundle: {path}{rid}")
            )

        def show_deploy_status(self, status: str, details: str | None = None) -> None:
            detail = f" — {details}" if details else ""
            if status.upper() in ("PASSED", "PROMOTED", "SUCCESS"):
                self.append_message(
                    CommandResultMessage(
                        command="deploy",
                        result=f"Deploy: {status}{detail}",
                    )
                )
            else:
                self.show_warning(f"Deploy: {status}{detail}")

        def show_section_break(self) -> None:
            self._write(self._safe_text("───────────────────────────────────────"))

        def clear_visible(self) -> None:
            try:
                self.query_one("#output-log", RichLog).clear()
            except Exception:
                pass

        def register_command_result(
            self,
            command: str,
            result: "CommandResult",
        ) -> None:
            try:
                from vnalpha.tui.research_navigation import build_artifact_states

                self._latest_artifact_states = build_artifact_states(command, result)
            except Exception as exc:  # noqa: BLE001
                self._capture_render_error(exc)

        def open_latest_artifact_detail(self) -> bool:
            if not self._latest_artifact_states:
                return False
            return self.open_artifact_detail(
                self._latest_artifact_states[-1].artifact_id
            )

        def open_artifact_detail(self, artifact_id: str) -> bool:
            state = self._artifact_state(artifact_id)
            if state is None:
                return False
            self._artifact_snapshot_stack.append(self._capture_visible_lines())
            self._artifact_stack.append(state)
            self._detail_mode = True
            self.clear_visible()
            self._write(self._artifact_renderable(state))
            return True

        def navigate_back(self) -> bool:
            if not self._artifact_stack:
                return False
            self._artifact_stack.pop()
            snapshot = (
                self._artifact_snapshot_stack.pop()
                if self._artifact_snapshot_stack
                else ()
            )
            self._detail_mode = bool(self._artifact_stack)
            self._restore_visible_lines(snapshot)
            return True

        def current_artifact_id(self) -> str | None:
            if not self._artifact_stack:
                return None
            return self._artifact_stack[-1].artifact_id

        def note_command_for_current_artifact(self) -> str | None:
            if not self._artifact_stack:
                return None
            return self._artifact_stack[-1].note_command

        def assistant_prompt_for_current_artifact(self) -> str | None:
            if not self._artifact_stack:
                return None
            return self._artifact_stack[-1].assistant_prompt

        def append_activity(
            self,
            text: str,
            detail: str | None = None,
            kind: str = "running",
            elapsed_ms: int | None = None,
        ) -> None:
            if elapsed_ms is not None and detail is None:
                detail = f"{elapsed_ms}ms"
            self._append_activity_line(text, detail=detail, kind=kind)

        def append_assistant_answer(self, answer: "AssistantAnswerMessage") -> None:
            self.append_message(answer)

        def render_messages(self) -> tuple["ConversationMessage", ...]:
            return tuple(self._messages)

        def clear_messages(self) -> None:
            self._messages.clear()

        def _render_typed_message(self, message: "ConversationMessage") -> None:
            from vnalpha.tui.models.conversation import MessageKind

            if message.kind == MessageKind.USER:
                self._render_user_message(message)
            elif message.kind == MessageKind.ASSISTANT:
                self._render_assistant_answer(message)
            elif message.kind == MessageKind.COMMAND_RESULT:
                self._render_command_result(message)
            elif message.kind == MessageKind.ACTIVITY:
                self._render_activity(message)
            elif message.kind == MessageKind.WARNING:
                self._render_warning(message)
            elif message.kind == MessageKind.ERROR:
                self._render_error(message)
            elif message.kind == MessageKind.APPROVAL_REQUEST:
                self._render_approval_request(message)
            else:
                self._write(self._safe_text(message.text))

        def _render_user_message(self, message: "UserMessage") -> None:
            if message.prompt_type == "slash":
                text = self._safe_text(f"$ {message.text}", style="dim")
            else:
                text = self._safe_text(f"❯ {message.text}", style="bold cyan")
            self._write(text)

        def _render_assistant_answer(self, message: "AssistantAnswerMessage") -> None:
            summary = message.summary or message.text
            self._write(self._safe_text("Summary: " + summary, style="bold green"))
            risks = message.risks_caveats or "No explicit caveats."
            self._write(self._safe_text(f"Risks: {risks}", style="yellow"))
            source_count, missing_count = message.source_counts()
            self._write(
                self._safe_text(
                    f"Sources: {source_count}  Missing data: {missing_count}"
                )
            )
            if message.basis:
                self._write(self._safe_text(f"Basis: {message.basis}"))
            if message.missing_data:
                self._write(self._safe_text("Missing data:"))
                for item in message.missing_data:
                    self._write(self._safe_text(f"  - {item}"))
            if message.grounded_source_refs:
                self._write(self._safe_text("Grounded source refs:"))
                for item in message.grounded_source_refs:
                    self._write(self._safe_text(f"  - {item}"))

        def _render_command_result(self, message: "CommandResultMessage") -> None:
            self._append_command_result(message.text)

        def _render_activity(self, message: "ActivityMessage") -> None:
            if message.detail == "running":
                text = f"⟳ {message.text}"
                style = "dim"
            elif message.detail == "done":
                text = f"✓ {message.text}"
                style = "green"
            else:
                text = message.text
                style = None
            if message.elapsed_ms is not None:
                text = f"{text} ({message.elapsed_ms}ms)"
            self._write(self._safe_text(text, style=style))

        def _render_warning(self, message: "WarningMessage") -> None:
            self._write(self._safe_text(message.text, style="yellow"))

        def _render_error(self, message: "ErrorMessage") -> None:
            self._write(self._safe_text(message.text, style="bold red"))

        def _render_approval_request(self, message: "ApprovalRequestMessage") -> None:
            self._write(self._safe_text("Approval required", style="bold magenta"))
            for idx, tool in enumerate(message.tools, start=1):
                self._write(self._safe_text(f"{idx}. {tool}"))
            if message.permissions:
                self._write(self._safe_text(f"Permissions: {message.permissions}"))
            self._write(self._safe_text("[A] Approve    [Esc] Cancel    [D] Details"))

        def _append_command_result(self, result: "RenderableType") -> None:
            if isinstance(result, str):
                result_text = result.strip()
                if result_text:
                    self._write(self._safe_text(result_text))
            else:
                self._write(result)

        def _append_activity_line(
            self, text: str, detail: str | None, kind: str
        ) -> None:
            if detail:
                text = f"{text} — {detail}"
            if kind == "done":
                label = f"✓ {text}"
                style = "green"
            elif kind == "running":
                label = f"⟳ {text}"
                style = "dim"
            else:
                label = text
                style = "yellow"
            self._write(self._safe_text(label, style=style))

        def _safe_text(self, value: str, style: str | None = None) -> Text:
            text = Text(escape_markup(value))
            if style:
                text.stylize(style)
            return text

        def _write(self, text: "RenderableType") -> None:
            try:
                self.query_one("#output-log", RichLog).write(text)
            except Exception as exc:  # noqa: BLE001
                self._capture_render_error(exc)

        def _scroll_log(self, method: str, amount: int) -> None:
            try:
                log = self.query_one("#output-log", RichLog)
                scroll = getattr(log, method, None)
                if not callable(scroll):
                    return
                for _ in range(max(1, amount)):
                    scroll()
            except Exception:  # noqa: BLE001
                pass

        def _scroll_to_boundary(self, method: str) -> None:
            try:
                log = self.query_one("#output-log", RichLog)
                scroll = getattr(log, method, None)
                if callable(scroll):
                    scroll()
            except Exception:  # noqa: BLE001
                pass

        def _capture_render_error(self, exc: Exception) -> None:
            try:
                from vnalpha.tui.routing.events import capture_render_error

                capture_render_error(exc)
            except Exception:
                pass

        def _artifact_state(self, artifact_id: str) -> "ArtifactDetailState" | None:
            for state in self._latest_artifact_states:
                if state.artifact_id == artifact_id:
                    return state
            return None

        def _artifact_renderable(
            self, state: "ArtifactDetailState"
        ) -> "RenderableType":
            from vnalpha.tui.research_navigation import artifact_detail_renderable

            return artifact_detail_renderable(state)

        def _capture_visible_lines(self) -> tuple[str, ...]:
            try:
                log = self.query_one("#output-log", RichLog)
            except Exception:
                return ()

            snapshot: list[str] = []
            for line in log.lines:
                snapshot.append(
                    getattr(line, "plain", getattr(line, "text", str(line)))
                )
            return tuple(snapshot)

        def _restore_visible_lines(self, snapshot: tuple[str, ...]) -> None:
            self.clear_visible()
            if not snapshot:
                return
            for line in snapshot:
                self._write(self._safe_text(line))

        def _rerender_messages(self) -> None:
            for message in self._messages:
                self._render_typed_message(message)

else:

    class OutputStream:  # type: ignore[no-redef]
        DEFAULT_CSS = ""

        def __init__(self, *, max_messages: int = 300, **kwargs) -> None:
            del kwargs
            self._max_messages = max(50, max_messages)
            self._messages: list[object] = []
            self._latest_artifact_states: tuple[object, ...] = ()
            self._artifact_stack: list[object] = []
            self._artifact_snapshot_stack: list[tuple[str, ...]] = []

        def append_message(self, message: "ConversationMessage") -> None:
            self._messages.append(message)
            if len(self._messages) > self._max_messages:
                self._messages = self._messages[-self._max_messages :]

        def show_user_input(self, text: str) -> None:
            self.append_message(text)

        def show_assistant_message(self, text: str, style: str | None = None) -> None:
            del text, style

        def show_command_result(self, command: str, result: "RenderableType") -> None:
            del command, result

        def show_error(self, message: str, source: str | None = None) -> None:
            del message, source

        def show_warning(self, message: str, source: str | None = None) -> None:
            del message, source

        def show_trace_event(self, event: "TraceEvent") -> None:
            del event

        def show_data_ensure_progress(
            self, step: str, status: str, detail: str = ""
        ) -> None:
            del step, status, detail

        def show_table_or_markup(self, markup: "RenderableType") -> None:
            del markup

        def show_repair_bundle(self, path: str, repair_id: str | None = None) -> None:
            del path, repair_id

        def show_deploy_status(self, status: str, details: str | None = None) -> None:
            del status, details

        def show_section_break(self) -> None:
            pass

        def clear_visible(self) -> None:
            pass

        def append_activity(
            self,
            text: str,
            detail: str | None = None,
            kind: str = "running",
            elapsed_ms: int | None = None,
        ) -> None:
            del text, detail, kind, elapsed_ms

        def append_assistant_answer(self, answer: "AssistantAnswerMessage") -> None:
            del answer

        def register_command_result(
            self, command: str, result: "CommandResult"
        ) -> None:
            del command, result

        def open_latest_artifact_detail(self) -> bool:
            return False

        def open_artifact_detail(self, artifact_id: str) -> bool:
            del artifact_id
            return False

        def navigate_back(self) -> bool:
            return False

        def current_artifact_id(self) -> str | None:
            return None

        def note_command_for_current_artifact(self) -> str | None:
            return None

        def assistant_prompt_for_current_artifact(self) -> str | None:
            return None

        def render_messages(self) -> tuple["ConversationMessage", ...]:
            return tuple(self._messages)

        def clear_messages(self) -> None:
            self._messages.clear()
