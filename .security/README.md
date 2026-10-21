# Static analysis baseline

`bandit-baseline.json` is the reviewed Bandit 1.9.4 baseline for deployed Python source (`petcare/`, `scripts/`, `main.py`, `run.py`, and `wsgi.py`). CI fails on findings that are not already represented in this baseline. It currently contains 38 findings and no High-severity findings.

The existing findings are reviewed exceptions, not a clean scan: B608 reports query fragments built from fixed code constants with user values passed separately as SQL parameters; B104 is the opt-in, validated LAN-camera bind; B404/B603 are the backup utility's fixed-argv Docker invocation and constant `sh -c` script with a validated database name; B105 matches throttle labels and a benchmark-only secret. When changing these code paths, re-review them and remove baseline entries as they are fixed. Do not refresh the baseline wholesale to make CI pass.

The CI pin is `bandit==1.9.4`. Upgrade the scanner deliberately, inspect new results, then regenerate this file only after review.
