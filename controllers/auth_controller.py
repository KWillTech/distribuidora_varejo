"""Controlador Qt para autenticação sem acesso direto ao banco."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from models.auth import AuthenticatedSession
from services.authentication import AuthenticationError, AuthenticationService


class AuthController(QObject):
    login_succeeded = Signal(object)
    login_failed = Signal(str)
    password_changed = Signal()
    password_change_failed = Signal(str)

    def __init__(self, service: AuthenticationService) -> None:
        super().__init__()
        self._service = service

    @Slot(str, str)
    def login(self, login: str, password: str) -> None:
        try:
            self.login_succeeded.emit(self._service.login(login, password))
        except AuthenticationError as exc:
            self.login_failed.emit(str(exc))

    @Slot(object, str, str)
    def change_password(self, session: AuthenticatedSession, current: str, new: str) -> None:
        try:
            self._service.change_own_password(session, current, new)
            self.password_changed.emit()
        except (AuthenticationError, ValueError) as exc:
            self.password_change_failed.emit(str(exc))

    def logout(self, session: AuthenticatedSession) -> None:
        self._service.logout(session)

