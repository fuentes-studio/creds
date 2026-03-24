"""Textual TUI app for creds."""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from textual.containers import Horizontal
from textual.binding import Binding

from creds.store import Store
from creds.registry import Registry
from creds.meta import MetaStore
from creds.tui.service_list import ServiceList
from creds.tui.details_panel import DetailsPanel
from creds.tui.add_dialog import AddDialog


class CredsApp(App):
    """creds — personal credential manager."""

    CSS = """
    Screen {
        layout: vertical;
    }
    #main-content {
        layout: horizontal;
        height: 1fr;
    }
    ServiceList {
        width: 38;
        border: solid $primary;
    }
    DetailsPanel {
        width: 1fr;
        border: solid $primary;
    }
    .badge-work {
        color: $warning;
    }
    .badge-personal {
        color: $success;
    }
    .status-set {
        color: $success;
    }
    .status-unset {
        color: $error;
    }
    .status-flagged {
        color: $error;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("a", "add_credential", "Add"),
        Binding("e", "edit_credential", "Edit"),
        Binding("r", "rotate_credential", "Rotate"),
        Binding("f", "flag_credential", "Flag"),
        Binding("c", "copy_value", "Copy"),
        Binding("v", "toggle_reveal", "Reveal"),
        Binding("m", "run_migrate", "Migrate"),
        Binding("W", "filter_work", "Work only"),
        Binding("P", "filter_personal", "Personal only"),
        Binding("/", "focus_filter", "Filter"),
        Binding("?", "show_help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.store = Store()
        self.registry = Registry()
        self.meta = MetaStore()
        self._context_filter: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="main-content"):
            yield ServiceList(store=self.store, registry=self.registry, meta=self.meta)
            yield DetailsPanel(store=self.store, registry=self.registry, meta=self.meta)
        yield Footer()

    def on_mount(self) -> None:
        self.title = "creds"
        self.sub_title = "credential manager"
        self.query_one(ServiceList).refresh_list()

    def on_service_list_selected(self, event: "ServiceList.Selected") -> None:
        self.query_one(DetailsPanel).show(event.service_id, event.instance)

    def action_add_credential(self) -> None:
        sl = self.query_one(ServiceList)
        service_id = sl.selected.service_id if sl.selected else None
        self.push_screen(
            AddDialog(store=self.store, registry=self.registry, meta=self.meta,
                      service_id=service_id, mode="add"),
            self._on_dialog_complete,
        )

    def action_edit_credential(self) -> None:
        sl = self.query_one(ServiceList)
        if not sl.selected:
            return
        self.push_screen(
            AddDialog(store=self.store, registry=self.registry, meta=self.meta,
                      service_id=sl.selected.service_id, instance=sl.selected.instance,
                      mode="edit"),
            self._on_dialog_complete,
        )

    def action_rotate_credential(self) -> None:
        sl = self.query_one(ServiceList)
        if not sl.selected:
            return
        self.push_screen(
            AddDialog(store=self.store, registry=self.registry, meta=self.meta,
                      service_id=sl.selected.service_id, instance=sl.selected.instance,
                      mode="rotate"),
            self._on_dialog_complete,
        )

    def action_flag_credential(self) -> None:
        sl = self.query_one(ServiceList)
        if not sl.selected:
            return
        svc = self.registry.get(sl.selected.service_id)
        if svc:
            for fld in svc.fields:
                self.meta.flag(sl.selected.service_id, sl.selected.instance, fld.id, reason="manual")
        sl.refresh_list()

    def action_copy_value(self) -> None:
        self.query_one(DetailsPanel).copy_first_field()

    def action_toggle_reveal(self) -> None:
        self.query_one(DetailsPanel).toggle_reveal()

    def action_filter_work(self) -> None:
        self._context_filter = None if self._context_filter == "work" else "work"
        self.query_one(ServiceList).set_context_filter(self._context_filter)

    def action_filter_personal(self) -> None:
        self._context_filter = None if self._context_filter == "personal" else "personal"
        self.query_one(ServiceList).set_context_filter(self._context_filter)

    def action_run_migrate(self) -> None:
        self.notify("Run 'creds migrate' in a terminal to migrate legacy entries.", timeout=5)

    def action_focus_filter(self) -> None:
        self.query_one(ServiceList).focus_filter()

    def action_show_help(self) -> None:
        self.notify(
            "a=Add  e=Edit  r=Rotate  f=Flag  c=Copy  v=Reveal  m=Migrate  "
            "W=Work  P=Personal  /=Filter  q=Quit",
            timeout=6,
        )

    def _on_dialog_complete(self, result: bool) -> None:
        if result:
            self.query_one(ServiceList).refresh_list()
            self.query_one(DetailsPanel).refresh_details()


def run_tui() -> None:
    CredsApp().run()
