"""Orchestrate cleanup of untouched, expired public-signup reservations."""

from petcare.repositories import tenant_cleanup_repo


def cleanup_expired_public_signups(connection, limit=100):
    """Delete only expired reservations that still have no user data."""
    candidates = tenant_cleanup_repo.list_expired_public_signup_candidates(connection, limit)
    return sum(
        tenant_cleanup_repo.delete_expired_unclaimed_signup(
            connection, candidate["tenant_id"], candidate["user_id"]
        )
        for candidate in candidates
    )
