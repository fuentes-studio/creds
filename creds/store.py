"""Unified credential store: Keychain + metadata."""
from creds import keychain
from creds.account import account_key
from creds.keychain import KeychainItemNotFound, KeychainError
from creds.meta import MetaStore
from creds.registry import Registry


class Store:
    def __init__(self) -> None:
        self.meta = MetaStore()
        self.registry = Registry()

    def get(
        self, service_id: str, instance: str = "", field_id: str = ""
    ) -> str:
        """Get credential value from Keychain."""
        svc = self.registry.get(service_id)
        if svc and not field_id:
            if len(svc.fields) == 1:
                field_id = svc.fields[0].id
            else:
                raise ValueError(
                    f"Service {service_id!r} has multiple fields — specify field_id"
                )
        acct = account_key(service_id, instance, field_id)
        return keychain.get(acct)

    def set(
        self,
        service_id: str,
        instance: str,
        field_id: str,
        value: str,
        context: str = "personal",
    ) -> None:
        """Store credential in Keychain and record metadata."""
        acct = account_key(service_id, instance, field_id)
        keychain.set(acct, value)
        self.meta.upsert(service_id, instance, field_id, context=context)

    def delete(self, service_id: str, instance: str, field_id: str) -> None:
        acct = account_key(service_id, instance, field_id)
        keychain.delete(acct)
        self.meta.delete(service_id, instance, field_id)

    def exists(
        self, service_id: str, instance: str = "", field_id: str = ""
    ) -> bool:
        svc = self.registry.get(service_id)
        if svc and not field_id:
            field_id = svc.fields[0].id
        acct = account_key(service_id, instance, field_id)
        return keychain.exists(acct)
