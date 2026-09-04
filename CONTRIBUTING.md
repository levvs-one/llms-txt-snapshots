# Contributing

Specific bug reports and small, tested changes are welcome.

## Set up

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Before opening a pull request, also run:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m pip check
```

A collector fix should include a regression test. A protocol change must update
`METHODS.md`, the collector version, and the schema version when the public
record shape changes.

For a data correction, include the snapshot version, target URL, exact field,
and a reproducible reason. A later change on the target site is a new
observation, not a correction to an older snapshot.

Do not add response bodies, credentials, personal data, or code that bypasses
access controls. Released snapshot files are not edited in place; corrections
are documented and followed by a new versioned run.
