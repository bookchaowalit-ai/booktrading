# BOO-123: complete offline strategy CI

Local verification on 2026-10-15 used Python 3.11.17 in an isolated environment.
The main strategy command now states its entire scope explicitly:

```sh
python -m pytest tests -q -o addopts= \
  --ignore=tests/test_command_center_contract.py \
  --disable-socket --allow-unix-socket
```

Overriding `addopts` avoids the default blanket `not integration` marker filter.
Only the named live contract file is excluded. A future marker cannot silently
remove another file from this CI command. pytest-socket blocks Internet sockets;
Unix sockets remain available for asyncio's local event-loop machinery.

The step supplies paper/testnet safety settings and disables AWS metadata lookup.
Local verification additionally used an allowlisted environment, empty AWS
configuration paths, no credentials, no external runtime roots and no services.
HTTP tests use in-process ASGI or mock transports; filesystem tests use temporary
fixtures. No provider, market-data or trading service was contacted.

## Reproduced failures and focused changes

1. Fresh installation of the original requirements selected PyArrow 26.0.0,
   which refused to import with the pinned NumPy 1.26.3. Three collection errors
   prevented the suite from running. The requirements now bound PyArrow below
   26; PyArrow 25.0.1 imports with the existing NumPy/pandas pins.
2. With `POLY_DRY_RUN=true`, two tests expecting simulated paper entries failed
   because that mode intentionally logs a would-trade instead. Those two tests
   now explicitly choose the in-memory paper-bookkeeping branch with a scoped
   monkeypatch. The separate dry-run tests still exercise their own mode.
   No application trading logic or runtime configuration was changed.

## Results

- Main strategy suite: **659 passed, 0 skipped** with network sockets disabled.
- Additional research suite: **34 passed, 1 optional integration skip**. The
  lake round trip requires extra lake dependencies/runtime outside this clone;
  this existing optional skip is separate from the main 659-test command.
- Existing Ruff undefined-name/syntax gate: passed.
- Existing focused Futures Ruff gate: passed.
- `git diff --check`: passed.

Hosted `ci-cd.yml` success on the final main commit is still required. No push,
hosted workflow, image build, deployment, credential access or provider call was
performed. The parent owns hosted verification and tracker updates.
