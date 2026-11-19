"""Command-line entry point for the encrypted tenant export worker."""

import argparse

from cryptography.fernet import Fernet, MultiFernet
from flask import Flask

from petcare.config import Config
from petcare.services.tenant_export_storage import validate_export_storage_config
from petcare.services.tenant_export_worker import dispatch_batch, maintenance, process_one, run_worker


def main():
    parser = argparse.ArgumentParser(description="Process queued PetCare tenant exports.")
    parser.add_argument("--once", action="store_true", help="process due exports then exit")
    parser.add_argument("--job-id", type=int, help="process one selected export job")
    parser.add_argument("--poll-seconds", type=int, default=3)
    args = parser.parse_args()
    app = Flask("petcare-tenant-export-worker")
    app.config.from_object(Config)
    validate_export_storage_config(app.config)
    key = str(app.config.get("TENANT_EXPORT_JOB_KEY", "")).strip()
    if app.config.get("APP_ENV") == "production":
        if not key:
            raise RuntimeError("Production requires TENANT_EXPORT_JOB_KEY for the export worker.")
        try:
            MultiFernet([
                Fernet(item.encode("ascii"))
                for item in [key, *app.config.get("TENANT_EXPORT_JOB_FALLBACK_KEYS", ())]
            ])
        except (UnicodeEncodeError, ValueError, TypeError) as exc:
            raise RuntimeError("TENANT_EXPORT_JOB_KEY must be a valid Fernet key.") from exc
    with app.app_context():
        if args.job_id is not None:
            print("Processed export job." if process_one(args.job_id) else "No due export job found.")
        elif args.once:
            count = dispatch_batch()
            maintenance()
            print(f"Processed {count} tenant export job(s).")
        else:
            run_worker(args.poll_seconds)


if __name__ == "__main__":
    main()
