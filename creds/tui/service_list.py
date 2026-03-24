"""Left panel: scrollable service tree with categories and status badges."""
from dataclasses import dataclass
from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Tree

from creds.meta import MetaStore
from creds.registry import Registry
from creds.store import Store


@dataclass
class ServiceSelection:
    service_id: str
    instance: str


class ServiceList(Widget):
    """Scrollable two-level tree: categories → services (→ instances)."""

    DEFAULT_CSS = """
    ServiceList {
        padding: 0 1;
    }
    Input {
        height: 3;
        margin: 0 0 1 0;
    }
    """

    selected: reactive[ServiceSelection | None] = reactive(None)

    class Selected(Message):
        def __init__(self, service_id: str, instance: str) -> None:
            super().__init__()
            self.service_id = service_id
            self.instance = instance

    def __init__(self, store: Store, registry: Registry, meta: MetaStore) -> None:
        super().__init__()
        self.store = store
        self.registry = registry
        self.meta = meta
        self._filter_text = ""
        self._context_filter: str | None = None

    def compose(self) -> ComposeResult:
        yield Input(placeholder="/ to filter...", id="filter-input")
        yield Tree("Services", id="service-tree")

    def on_mount(self) -> None:
        self.refresh_list()

    def refresh_list(self) -> None:
        tree = self.query_one(Tree)
        tree.clear()
        tree.root.expand()

        warn_days = int(self.meta.setting("rotation_warn_days") or "90")
        overdue_days = int(self.meta.setting("rotation_overdue_days") or "180")
        now = datetime.now(timezone.utc)

        by_cat = self.registry.by_category()
        total = 0
        set_count = 0

        for category, services in by_cat.items():
            cat_node = tree.root.add(category, expand=True)

            for svc in services:
                if self._filter_text and self._filter_text.lower() not in svc.label.lower():
                    continue

                if not svc.multi_instance:
                    field_id = svc.fields[0].id if svc.fields else "value"
                    ctx = svc.context
                    if self._context_filter and ctx not in (self._context_filter, "both"):
                        continue

                    is_set = self.store.exists(svc.id, "", field_id)
                    cred_meta = self.meta.get(svc.id, "", field_id)
                    age_flag = self._age_flag(cred_meta, now, warn_days, overdue_days)
                    flagged = cred_meta and cred_meta.status == "flagged"

                    status = "+" if is_set else "-"
                    badge = "[W]" if ctx == "work" else "[B]" if ctx == "both" else "[P]"
                    parts = [status, svc.label, badge]
                    if age_flag:
                        parts.append(age_flag)
                    if flagged:
                        parts.append("[F]")
                    label = " ".join(parts)

                    cat_node.add_leaf(label, data=ServiceSelection(svc.id, ""))
                    total += 1
                    if is_set:
                        set_count += 1
                else:
                    svc_node = cat_node.add(f"  {svc.label}", expand=False)
                    instances_meta = self.meta.all_for_service(svc.id)
                    instances = list({m.instance for m in instances_meta if m.instance})

                    for instance in instances:
                        if self._context_filter:
                            m = self.meta.get(svc.id, instance, svc.fields[0].id if svc.fields else "value")
                            if m and m.context not in (self._context_filter, "both"):
                                continue

                        all_set = all(self.store.exists(svc.id, instance, f.id) for f in svc.fields)
                        cred_meta = self.meta.get(svc.id, instance, svc.fields[0].id if svc.fields else "value")
                        ctx = cred_meta.context if cred_meta else svc.context
                        age_flag = self._age_flag(cred_meta, now, warn_days, overdue_days)
                        flagged = cred_meta and cred_meta.status == "flagged"

                        status = "+" if all_set else "-"
                        badge = "[W]" if ctx == "work" else "[P]"
                        parts = [status, instance, badge]
                        if age_flag:
                            parts.append(age_flag)
                        if flagged:
                            parts.append("[F]")

                        svc_node.add_leaf(" ".join(parts), data=ServiceSelection(svc.id, instance))
                        total += 1
                        if all_set:
                            set_count += 1

        try:
            self.app.sub_title = f"{set_count}/{total} credentials set"
        except Exception:
            pass

    def _age_flag(self, cred_meta, now, warn_days, overdue_days) -> str:
        if not cred_meta:
            return ""
        try:
            updated = datetime.fromisoformat(cred_meta.updated_at)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            days = (now - updated).days
            if days >= overdue_days:
                return "[OLD]"
            if days >= warn_days:
                return "[WARN]"
        except Exception:
            pass
        return ""

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if event.node.data and isinstance(event.node.data, ServiceSelection):
            self.selected = event.node.data
            self.post_message(self.Selected(event.node.data.service_id, event.node.data.instance))

    def set_context_filter(self, context: str | None) -> None:
        self._context_filter = context
        self.refresh_list()

    def focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self._filter_text = event.value
        self.refresh_list()
