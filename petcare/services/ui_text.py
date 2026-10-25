"""Copy for the new modules, kept separate from the user's in-progress i18n file."""

from petcare.i18n import current_locale


def ui_text(vietnamese, english):
    return english if current_locale() == "en" else vietnamese
