"""Right panel: credential details view."""
import threading
import time
from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from creds.formatting import age_label
from creds.keychain import KeychainItemNotFound
from creds.meta import MetaStore
from creds.registry import Registry
from creds.store import Store


class DetailsPanel(Widget):
    """Shows full detail for the selected credential."""

    DEFAULT_CSS = """
    DetailsPanel {
        padding: 1 2;
    }
    """

    def __init__(self, store: Store, registry: Registry, meta: MetaStore) -> None:
        super().__init__()
        self.store = store
        self.registry = registry
        self.meta = meta
        self._service_id: str | None = None
        self._instance: str = ""
        self._revealed: bool = False

    def compose(self) -> ComposeResult:
        yield Static("Select a service to view details.", id="detail-content")

    def show(self, service_id: str, instance: str) -> None:
        self._service_id = service_id
        self._instance = instance
        self._revealed = False  # reset reveal state when switching services
        self.refresh_details()

    def toggle_reveal(self) -> None:
        """Toggle between masked and revealed credential values."""
        self._revealed = not self._revealed
        self.refresh_details()

    def refresh_details(self) -> None:
        content = self.query_one("#detail-content", Static)
        if not self._service_id:
            content.update("Select a service to view details.")
            return

        svc = self.registry.get(self._service_id)
        if not svc:
            content.update(f"Unknown service: {self._service_id}")
            return

        warn_days = int(self.meta.setting("rotation_warn_days") or "90")
        overdue_days = int(self.meta.setting("rotation_overdue_days") or "180")
        now = datetime.now(timezone.utc)

        instance_label = f" / {self._instance}" if self._instance else ""
        badge = "[W]" if svc.context == "work" else "[B]" if svc.context == "both" else "[P]"
        eye = "👁 [yellow]REVEALED[/yellow]" if self._revealed else "🔒 masked"
        lines = [f"[bold]{svc.label}{instance_label}[/bold]  {badge}  {eye}\n"]

        for fld in svc.fields:
            m = self.meta.get(self._service_id, self._instance, fld.id)
            is_set = self.store.exists(self._service_id, self._instance, fld.id)

            lines.append(f"[dim]{fld.label}[/dim]")

            if is_set:
                try:
                    value = self.store.get(self._service_id, self._instance, fld.id)
                    if self._revealed:
                        display = value
                    elif len(value) > 12:
                        display = value[:4] + "••••••••" + value[-4:]
                    else:
                        display = "••••"
                except KeychainItemNotFound:
                    display = "(error reading)"
                    value = ""

                age_str = ""
                rotation_note = ""
                if m:
                    try:
                        updated = datetime.fromisoformat(m.updated_at)
                        if updated.tzinfo is None:
                            updated = updated.replace(tzinfo=timezone.utc)
                        days = (now - updated).days
                        age_str = age_label(days)
                        if days >= overdue_days:
                            rotation_note = "[red]Rotation OVERDUE[/red]"
                        elif days >= warn_days:
                            rotation_note = "[yellow]Rotation recommended[/yellow]"
                    except Exception:
                        pass

                status_line = "[green]set[/green]"
                if m and m.status == "flagged":
                    status_line = "[red]FLAGGED[/red]"
                    if m.flag_reason:
                        status_line += f" — {m.flag_reason}"

                lines.append(f"  Status:   {status_line}")
                lines.append(f"  Value:    {display}")
                lines.append(f"  Env var:  {fld.env_var}")
                if age_str:
                    lines.append(f"  Updated:  {age_str}")
                if rotation_note:
                    lines.append(f"  {rotation_note}")
            else:
                lines.append("  [red]not set[/red]")
                lines.append(f"  Env var:  {fld.env_var}")

            lines.append("")

        if svc.hint:
            lines.append(f"[dim]Hint:[/dim]  {svc.hint}\n")

        reveal_hint = "v=Hide" if self._revealed else "v=Reveal"
        lines.append(f"[dim]e=Edit  r=Rotate  f=Flag  c=Copy  {reveal_hint}  q=Quit[/dim]")
        content.update("\n".join(lines))

    def copy_first_field(self) -> None:
        if not self._service_id:
            return
        svc = self.registry.get(self._service_id)
        if not svc or not svc.fields:
            return
        try:
            import pyperclip
            value = self.store.get(self._service_id, self._instance, svc.fields[0].id)
            pyperclip.copy(value)
            self.app.notify(f"Copied {svc.fields[0].label} to clipboard (clears in 30s)", timeout=3)

            def _clear() -> None:
                time.sleep(30)
                try:
                    if pyperclip.paste() == value:
                        pyperclip.copy("")
                except Exception:
                    pass

            threading.Thread(target=_clear, daemon=True).start()
        except Exception as e:
            self.app.notify(f"Copy failed: {e}", severity="error")
