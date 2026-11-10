"""PetCare Manager Flask package and backwards-compatible app factory export."""

from petcare.app_factory import create_app, csrf

__all__ = ["create_app", "csrf"]
