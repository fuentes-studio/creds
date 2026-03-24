"""Modal dialog for adding/editing/rotating credentials."""
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select

from creds.meta import MetaStore
from creds.registry import Registry
from creds.store import Store


class AddDialog(ModalScreen[bool]):
    """Modal for adding, editing, or rotating a credential."""

    DEFAULT_CSS = """
    AddDialog {
        align: center middle;
    }
    #dialog {
        background: $surface;
        border: solid $primary;
        padding: 1 2;
        width: 60;
        max-height: 32;
    }
    .dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .field-label {
        margin-top: 1;
        color: $text-muted;
    }
    #buttons {
        margin-top: 1;
    }
    Button {
        margin-right: 1;
    }
    """

    def __init__(
        self,
        store: Store,
        registry: Registry,
        meta: MetaStore,
        service_id: Optional[str] = None,
        instance: str = "",
        mode: str = "add",
    ) -> None:
        super().__init__()
        self.store = store
        self.registry = registry
        self.meta = meta
        self.service_id = service_id
        self.instance = instance
        self.mode = mode

    def compose(self) -> ComposeResult:
        svc = self.registry.get(self.service_id) if self.service_id else None
        titles = {"add": "Add Credential", "edit": "Edit Credential", "rotate": "Rotate Credential"}
        title = titles.get(self.mode, "Credential")

        with Vertical(id="dialog"):
            yield Label(title, classes="dialog-title")

            if not self.service_id:
                yield Label("Service ID", classes="field-label")
                yield Input(placeholder="e.g. anthropic", id="svc-input")

            if svc and svc.multi_instance and not self.instance:
                yield Label("Instance name (workspace / project)", classes="field-label")
                yield Input(placeholder="e.g. Acme", id="instance-input")

            yield Label("Context", classes="field-label")
            default_ctx = "personal"
            if svc:
                default_ctx = svc.context if svc.context != "both" else "personal"
            yield Select(
                [("personal", "personal"), ("work", "work")],
                value=default_ctx,
                id="context-select",
            )

            if svc:
                if svc.hint and self.mode == "add":
                    yield Label(f"Hint: {svc.hint}", classes="field-label")
                for fld in svc.fields:
                    yield Label(fld.label, classes="field-label")
                    yield Input(
                        placeholder=f"Enter {fld.label}",
                        password=fld.secret,
                        id=f"field-{fld.id}",
                    )
            else:
                yield Label("Value", classes="field-label")
                yield Input(placeholder="Credential value", password=True, id="field-value")

            with Horizontal(id="buttons"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(False)
        elif event.button.id == "save-btn":
            self._save()

    def _save(self) -> None:
        service_id = self.service_id
        if not service_id:
            try:
                service_id = self.query_one("#svc-input", Input).value.strip()
            except Exception:
                pass
            if not service_id:
                self.app.notify("Service ID is required.", severity="error")
                return

        instance = self.instance
        if not instance:
            try:
                instance = self.query_one("#instance-input", Input).value.strip()
            except Exception:
                pass

        try:
            context = str(self.query_one("#context-select", Select).value)
        except Exception:
            context = "personal"

        svc = self.registry.get(service_id)
        if svc:
            for fld in svc.fields:
                try:
                    inp = self.query_one(f"#field-{fld.id}", Input)
                    value = inp.value.strip()
                    if not value:
                        self.app.notify(f"{fld.label} is required.", severity="error")
                        return
                    self.store.set(service_id, instance, fld.id, value, context=context)
                except Exception as e:
                    self.app.notify(f"Error saving {fld.id}: {e}", severity="error")
                    return
        else:
            try:
                inp = self.query_one("#field-value", Input)
                value = inp.value.strip()
                if not value:
                    self.app.notify("Value is required.", severity="error")
                    return
                self.store.set(service_id, instance, "value", value, context=context)
            except Exception as e:
                self.app.notify(f"Error: {e}", severity="error")
                return

        self.app.notify("Saved.")
        self.dismiss(True)
