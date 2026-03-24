"""creds CLI — click commands."""
import sys
from datetime import datetime, timezone
import click
from creds import __version__
from creds.formatting import age_label
from creds.store import Store
from creds.keychain import KeychainItemNotFound
from creds.meta import MetaStore
from creds.migrate import build_migration_plan, migrate_entry
from creds.registry import Registry


@click.group(invoke_without_command=True)
@click.version_option(version=__version__)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Personal credential manager. Run without args to open TUI."""
    if ctx.invoked_subcommand is None:
        from creds.tui.app import run_tui
        run_tui()


@main.command()
@click.argument("service")
@click.argument("instance", default="")
@click.argument("field", default="")
def get(service: str, instance: str, field: str) -> None:
    """Get a credential value (stdout only). Exit 1 if missing."""
    store = Store()
    try:
        value = store.get(service, instance, field)
        click.echo(value, nl=False)
    except KeychainItemNotFound as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@main.command()
@click.argument("service")
@click.argument("instance", default="")
def check(service: str, instance: str) -> None:
    """Exit 0 if credential is set, exit 1 if not. No output."""
    store = Store()
    if store.exists(service, instance):
        sys.exit(0)
    sys.exit(1)


@main.command()
@click.option("--dry-run", is_flag=True, help="Show what would be migrated without writing.")
@click.option("--yes", "-y", is_flag=True, help="Auto-confirm all migrations.")
def migrate(dry_run: bool, yes: bool) -> None:
    """One-time migration from legacy Keychain entries to canonical names."""
    registry = Registry()
    store = Store()

    click.echo("\nScanning legacy Keychain entries...\n")
    services_with_legacy = [s for s in registry.all() if s.legacy_keys]
    found, not_found = build_migration_plan(services_with_legacy)

    if not found:
        click.echo("Nothing found in legacy locations. Nothing to migrate.")
        if not_found:
            click.echo(f"\n{len(not_found)} services have no legacy keys to scan.")
            click.echo("Run 'creds' to add them manually.")
        return

    click.echo(f"Found {len(found)} credential(s) in legacy locations:\n")
    for r in found:
        masked = r.value[:8] + "..." if len(r.value) > 8 else "***"
        click.echo(
            f"  +  {r.service.label:20s}  "
            f"[{r.legacy_key.service} / {r.legacy_key.account}]  ->  "
            f"io.creds.store / {r.service.id}.{r.field_id}"
            f"  ({masked})"
        )

    if dry_run:
        click.echo("\n[dry-run] No changes made.")
        return

    click.echo()
    if not yes and not click.confirm("Migrate all found entries?"):
        click.echo("Aborted.")
        return

    migrated = 0
    for r in found:
        context = r.service.context if r.service.context != "both" else "personal"
        try:
            migrate_entry(r, store, context=context)
            click.echo(f"  +  Migrated {r.service.label}")
            migrated += 1
        except Exception as e:
            click.echo(f"  x  Failed {r.service.label}: {e}", err=True)

    click.echo(f"\nMigrated {migrated}/{len(found)} entries.")

    if not_found:
        click.echo(f"\n{len(not_found)} service(s) not found in legacy locations:")
        for svc in not_found:
            click.echo(f"  - {svc.label}")
        click.echo("\nRun 'creds add <service>' or open 'creds' TUI to add them.")


# ─── audit ────────────────────────────────────────────────────────────────────


def _get_instances(meta: MetaStore, service_id: str) -> list[str]:
    metas = meta.all_for_service(service_id)
    seen: set[str] = set()
    result: list[str] = []
    for m in metas:
        if m.instance and m.instance not in seen:
            seen.add(m.instance)
            result.append(m.instance)
    return result or [""]


@main.command()
@click.option("--missing", is_flag=True, help="Show only unset services.")
@click.option("--required", "req_only", is_flag=True, help="Show only required services.")
@click.option("--stale", is_flag=True, help="Show only rotation-overdue services.")
@click.option("--quiet", is_flag=True, help="Exit 1 if anything is missing/flagged, silent.")
def audit(missing: bool, req_only: bool, stale: bool, quiet: bool) -> None:
    """Show credential status for all services."""
    registry = Registry()
    store = Store()
    meta = MetaStore()

    warn_days = int(meta.setting("rotation_warn_days") or "90")
    overdue_days = int(meta.setting("rotation_overdue_days") or "180")
    now = datetime.now(timezone.utc)

    rows = []
    issues = 0

    for svc in registry.all():
        if req_only and not svc.required:
            continue
        instances = [""] if not svc.multi_instance else _get_instances(meta, svc.id)
        for instance in instances:
            for fld in svc.fields:
                is_set = store.exists(svc.id, instance, fld.id)
                cred_meta = meta.get(svc.id, instance, fld.id)

                age_str = ""
                age_flag = ""
                if cred_meta:
                    updated = datetime.fromisoformat(cred_meta.updated_at)
                    if updated.tzinfo is None:
                        updated = updated.replace(tzinfo=timezone.utc)
                    days = (now - updated).days
                    age_str = age_label(days)
                    if days >= overdue_days:
                        age_flag = "OVERDUE"
                    elif days >= warn_days:
                        age_flag = "WARN"

                status = "+" if is_set else "-"
                flag_str = ""
                if cred_meta and cred_meta.status == "flagged":
                    flag_str = " [FLAGGED]"
                    issues += 1
                if not is_set:
                    issues += 1

                inst_label = f"[{instance}]" if instance else ""
                label = f"{svc.label} {inst_label}".strip()
                rows.append({
                    "label": label,
                    "field": fld.id,
                    "status": status,
                    "context": svc.context,
                    "age": age_str,
                    "age_flag": age_flag,
                    "flag_str": flag_str,
                    "is_set": is_set,
                })

    if stale:
        rows = [r for r in rows if r["age_flag"]]
    if missing:
        rows = [r for r in rows if not r["is_set"]]

    if quiet:
        sys.exit(1 if issues > 0 else 0)

    if not rows:
        click.echo("Nothing to show.")
        return

    for r in rows:
        click.echo(
            f"  {r['status']}  {r['label']:<30s}"
            f"{r['field']:<20s}"
            f"[{r['context']:<8s}]"
            f"  {r['age']:<12s}"
            f"  {r['age_flag']:<8s}"
            f"{r['flag_str']}"
        )


# ─── env ──────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--work", "context_filter", flag_value="work", help="Work credentials only.")
@click.option("--personal", "context_filter", flag_value="personal", help="Personal only.")
def env(context_filter: str) -> None:
    """Print export statements for all stored credentials. Use: eval $(creds env)"""
    registry = Registry()
    store = Store()
    meta = MetaStore()

    for svc in registry.all():
        cred_meta_list = meta.all_for_service(svc.id)
        instances: list[str] = (
            list({m.instance for m in cred_meta_list if m.instance})
            if svc.multi_instance else [""]
        )
        if not instances:
            instances = [""]

        for instance in instances:
            for fld in svc.fields:
                if context_filter:
                    m = meta.get(svc.id, instance, fld.id)
                    if m and m.context != context_filter:
                        continue
                if not store.exists(svc.id, instance, fld.id):
                    continue
                try:
                    value = store.get(svc.id, instance, fld.id)
                    env_var = fld.env_var
                    if instance:
                        env_var = f"{fld.env_var}_{instance.upper().replace(' ', '_').replace('-', '_')}"
                    # POSIX-safe: escape any single quotes in the value
                    safe_value = value.replace("'", "'\\''")
                    click.echo(f"export {env_var}='{safe_value}'")
                except Exception as e:
                    click.echo(f"# Warning: could not read {svc.id}.{fld.id}: {e}", err=True)


# ─── flag / unflag ────────────────────────────────────────────────────────────

@main.command()
@click.argument("service")
@click.argument("instance", default="")
@click.option("--field", "field_id", default="", help="Specific field to flag.")
@click.option("--reason", default="", help="Reason for flagging.")
def flag(service: str, instance: str, field_id: str, reason: str) -> None:
    """Mark a credential as suspect (e.g., after a 401 error)."""
    meta = MetaStore()
    registry = Registry()
    svc = registry.get(service)
    fields = [field_id] if field_id else ([f.id for f in svc.fields] if svc else ["value"])
    for f in fields:
        meta.flag(service, instance, f, reason=reason)
    click.echo(f"Flagged {service}{f'[{instance}]' if instance else ''} — run: creds audit")


@main.command()
@click.argument("service")
@click.argument("instance", default="")
@click.option("--field", "field_id", default="", help="Specific field to unflag.")
def unflag(service: str, instance: str, field_id: str) -> None:
    """Clear a flag on a credential."""
    meta = MetaStore()
    registry = Registry()
    svc = registry.get(service)
    fields = [field_id] if field_id else ([f.id for f in svc.fields] if svc else ["value"])
    for f in fields:
        meta.unflag(service, instance, f)
    click.echo(f"Cleared flag for {service}{f'[{instance}]' if instance else ''}")


# ─── add ──────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("service", required=False)
def add(service: str) -> None:
    """Interactively add or update a credential."""
    registry = Registry()
    store = Store()

    if not service:
        services = registry.all()
        click.echo("\nAvailable services:")
        for i, svc in enumerate(services):
            click.echo(f"  {i+1:2d}. {svc.label} ({svc.id})")
        choice = click.prompt("\nService number or ID")
        try:
            idx = int(choice) - 1
            service = services[idx].id
        except (ValueError, IndexError):
            service = choice

    svc = registry.get(service)
    if not svc:
        click.echo(f"Unknown service: {service!r}. Adding as custom credential.")
        context = click.prompt("Context", type=click.Choice(["personal", "work"]), default="personal")
        value = click.prompt(f"Value for {service}", hide_input=True, confirmation_prompt=True)
        store.set(service, "", "value", value, context=context)
        click.echo(f"Saved {service}")
        return

    instance = ""
    if svc.multi_instance:
        instance = click.prompt("Instance name (e.g., workspace or project name)")

    default_ctx = svc.context if svc.context != "both" else "personal"
    context = click.prompt(
        "Context", type=click.Choice(["personal", "work"]), default=default_ctx
    )

    if svc.hint:
        click.echo(f"\nHint: {svc.hint}\n")

    for fld in svc.fields:
        value = click.prompt(
            fld.label,
            hide_input=fld.secret,
            confirmation_prompt=fld.secret,
        )
        store.set(svc.id, instance, fld.id, value, context=context)

    label = f"{svc.label}{f' [{instance}]' if instance else ''}"
    click.echo(f"\nSaved {label}")


# ─── set (non-interactive) ────────────────────────────────────────────────────

@main.command(name="set")
@click.argument("service")
@click.argument("value")
@click.argument("instance", default="")
@click.option("--field", "field_id", default="", help="Specific field (for multi-field services).")
@click.option("--context", "ctx", type=click.Choice(["personal", "work"]), default="personal")
def set_cmd(service: str, value: str, instance: str, field_id: str, ctx: str) -> None:
    """Set a credential non-interactively (for scripting)."""
    registry = Registry()
    store = Store()
    svc = registry.get(service)
    fid = field_id or (svc.fields[0].id if svc and svc.fields else "value")
    store.set(service, instance, fid, value, context=ctx)
    click.echo(f"Set {service}.{fid}", err=True)
