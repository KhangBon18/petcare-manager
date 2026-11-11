# Academic demo launcher

The Phase 6.2 classroom workflow is maintained in [the Vietnamese demo script](docs/ACADEMIC_DEMO_SCRIPT.md) and [the demo readiness report](docs/PHASE62_DEMO_READINESS.md).

From the repository root, activate a virtual environment installed from the locked requirements, then run:

```sh
scripts/demo/classroom.sh --target qa
```

The launcher requires Docker Compose and a deliberate `qa` target. It prompts for separate demo account passwords without echoing them, creates a new MySQL `_test` schema in a disposable Compose project, uses only local media storage and a loopback Vision mock, and starts the application plus its local workers. Enter `r` in the launcher terminal to reset only that temporary QA database and its owned storage; enter `q` or press Ctrl-C for clean shutdown.

Do not replace the QA connection with a development or production database. The application seed refuses to run without explicit demo mode, environment-matched `_dev`/`_test` schema, and separately supplied passwords.
