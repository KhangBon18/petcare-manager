"""Command-line entry point for the email outbox worker."""

import argparse

from flask import Flask
from petcare.config import Config
from petcare.services.mail_service import validate_production_config, validate_runtime_config
from petcare.services.mail_outbox_worker import dispatch_batch, run_maintenance, run_worker


def main():
    parser = argparse.ArgumentParser(description="Deliver queued PetCare Manager email.")
    parser.add_argument("--once", action="store_true", help="process due messages then exit")
    parser.add_argument("--poll-seconds", type=int, default=5)
    args = parser.parse_args()
    app = Flask("petcare-email-worker")
    app.config.from_object(Config)
    validate_runtime_config(app.config)
    if app.config.get("APP_ENV") == "production":
        validate_production_config(app.config)
    with app.app_context():
        if args.once:
            processed = dispatch_batch()
            run_maintenance()
            print(f"Processed {processed} due email message(s).")
        else:
            run_worker(args.poll_seconds)


if __name__ == "__main__":
    main()
