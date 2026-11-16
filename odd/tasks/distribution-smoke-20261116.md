# APP mini-distribution smoke · 2026-11-16

## Scope

This isolated increment tests the existing Linux source installer and the app's
loopback runtime in a temporary HOME. It does not modify installer behavior or
publish a binary. It distinguishes the local APP from OpenWorld's Android TWA.

Claim base: `41433ccb8e60f8e3ffaf6266814fe7dcb84c9adf` (`origin/main` and the
remote `main` observed equal). Worktree branch:
`codex/app-mini-distribution-smoke-20261116`.

## Existing pieces inspected

- `empaquetado/install.sh` clones or fast-forward-updates the repository, then
  invokes `bin/instalar-pc`; it does not install Python, Ollama, or system
  packages. Its Linux path was exercised locally by the test.
- `bin/instalar-pc` creates a desktop entry and launcher. The smoke invokes the
  server directly with a temporary database and loopback bind; it never calls
  the desktop launcher or touches the real user's HOME.
- `casa.py` keeps user data under `~/.preceptoros`, outside the source tree.
- `empaquetado/install.ps1` explicitly says Windows is not tested.
- `INSTALL_ANDROID.md` says Termux is the available path and a native APK does
  not exist. A separately distributed OpenWorld TWA is not a local AI app.

## Reproducible check

From the repository root:

```sh
python3 -B -m unittest tests.test_distribution_smoke -v
```

The Linux test uses a local repository source override and a temporary HOME,
starts `bin/preceptoros-pwa` on `127.0.0.1`, checks `/api/estado` and `/`, stops
that exact child process, reruns the installer, and checks that the seeded
SQLite memory records are unchanged. It uses only standard library code.

Measured environment: Linux x86_64, Python 3.14.4, Git available. The test
exercises the current `main` source installer, not an externally downloaded
release binary. The run does not load a model or send data off-device.

## Limits

- `git pull --ff-only` is observed as the current update mechanism; it is not a
  signed release-manifest updater. This smoke does not claim authenticated
  artifact origin or safe update against arbitrary pre-existing Git hooks.
- The reinstall leg is a no-op fast-forward against the same local source; it
  does not prove that a newer release was installed. There is no signed release
  manifest or app-side updater implementation in this scope.
- No update button or app-side signed updater is implemented in this scope.
- No model is installed or invoked, so chatbot inference is `NO_DATA(model_inference_not_exercised)`.
- Windows, macOS, and native Android install remain `NO_DATA(platform_runtime_not_available)`.
- No release artifact is built, published, or run.
- Node 0 correlation is separate and remains gated on Claude's exact-file ACK.

## Receipt

- `python3 -B -m unittest tests.test_distribution_smoke -v`: **4/4 PASS ×2**.
- `./bin/pruebas`: **2,089 tests, 173 suites, 6 corridors, exit 0 ×2** after
  adding this suite to the canonical `UNITTEST` list. The gate reported **9
  skips**; causes are listed in the Mesa receipt. Its registered sabotage
  runs detected **47/47** mutations in 7 suites on both full runs.
- `git diff --check`: PASS.
- The first test draft compared the whole SQLite file digest and went RED
  after the app opened the database in WAL mode. That was file-layout churn,
  not loss of the saved record. The final invariant compares persisted memory
  rows, and the deliberate delete-memory mutation is caught.
- This is a synthetic local integration smoke, not proof of external install,
  model inference, signed updates, or a native Android package.
