from __future__ import annotations

import secrets
from dataclasses import dataclass

from llm_operations_lab.config import ApplicationPolicy
from llm_operations_lab.errors import AuthenticationError


@dataclass(frozen=True, slots=True)
class ApplicationIdentity:
    application_id: str
    policy: ApplicationPolicy


class Authenticator:
    def __init__(self, applications: dict[str, ApplicationPolicy]) -> None:
        self._applications = applications

    def authenticate(self, presented_key: str | None) -> ApplicationIdentity:
        if not presented_key:
            raise AuthenticationError("chave de API ausente ou inválida")
        for application_id, policy in self._applications.items():
            expected = policy.api_key.get_secret_value()
            if secrets.compare_digest(presented_key, expected):
                return ApplicationIdentity(application_id=application_id, policy=policy)
        raise AuthenticationError("chave de API ausente ou inválida")

