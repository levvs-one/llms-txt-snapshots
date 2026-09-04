# Contributing

Corrections and protocol critiques are welcome when they are specific and reproducible.

## Data correction

Open an issue or pull request containing:

1. the target URL and snapshot date;
2. the exact field believed to be wrong;
3. a command, response header, or public permalink that reproduces the discrepancy;
4. whether the difference is a collection error or a later website change.

Released snapshots are immutable. Confirmed collector errors are documented in a correction note and fixed in the next dated snapshot. Ordinary changes on a target site are new observations, not retroactive errors.

## Code changes

Run the standard-library test suite before submitting a change:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Protocol-changing pull requests must update `METHODOLOGY.md`, increment the protocol or collector version, and explain how comparability with earlier snapshots is affected.

Do not add stored page bodies, authentication material, personal data, or code intended to bypass access controls.

