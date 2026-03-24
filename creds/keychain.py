"""macOS Keychain wrapper using the `security` CLI."""
import subprocess

SERVICE = "io.creds.store"


class KeychainItemNotFound(Exception):
    pass


class KeychainError(Exception):
    pass


def get(account: str) -> str:
    """Retrieve a secret from the Keychain. Raises KeychainItemNotFound if missing."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.rstrip("\n")
    if result.returncode == 44 or "could not be found" in result.stderr:
        raise KeychainItemNotFound(f"No Keychain item for account {account!r}")
    raise KeychainError(f"security error: {result.stderr.strip()}")


def set(account: str, value: str) -> None:
    """Store a secret in the Keychain (delete-then-add for idempotency)."""
    # Delete existing item first (ignore errors — item may not exist)
    subprocess.run(
        ["security", "delete-generic-password", "-s", SERVICE, "-a", account],
        capture_output=True,
    )
    result = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-s", SERVICE,
            "-a", account,
            "-w", value,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise KeychainError(f"Failed to add Keychain item: {result.stderr.strip()}")


def delete(account: str) -> None:
    """Delete a Keychain item. Raises KeychainItemNotFound if missing."""
    result = subprocess.run(
        ["security", "delete-generic-password", "-s", SERVICE, "-a", account],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise KeychainItemNotFound(f"No Keychain item for account {account!r}")


def exists(account: str) -> bool:
    """Return True if the Keychain item exists."""
    try:
        get(account)
        return True
    except KeychainItemNotFound:
        return False
