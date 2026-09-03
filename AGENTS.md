# AGENTS.md

Guidance for AI agents (Claude Code, Copilot, Cursor, etc.) working in this repository.

## What this repo is

A GitHub template for **HACS-compatible Home Assistant custom integrations**.
The integration source lives in `custom_components/<domain>/`.

If `custom_components/integration_blueprint/` is still present, bootstrap has not
been done yet — complete the **Bootstrap** section below before doing any real work.

## Bootstrap (one-off, first clone only)

### 1. Replace placeholders

Follow the **placeholder table in `README.md`** (section "Replace the placeholders")
to do a find-and-replace across the whole repository, then rename the directory:

```bash
git mv custom_components/integration_blueprint "custom_components/<your-domain>"
```

### 2. Configure the repository (requires GitHub CLI)

```bash
OWNER=your-github-username
REPO=your-repo-name

# Allow release-please to open the Release PR
# (Settings → Actions → General → Workflow permissions → allow PR creation)
gh api -X PUT "/repos/$OWNER/$REPO/actions/permissions/workflow" \
  -F default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=true

# Add the HACS-required description and topics
gh repo edit "$OWNER/$REPO" \
  --description "A short description of your integration" \
  --add-topic home-assistant \
  --add-topic hacs \
  --add-topic home-assistant-custom \
  --add-topic integration
```

Without step 1: release-please fails with `403` when opening a Release PR.
Without step 2: the `Validate` workflow's HACS job fails — a missing description
causes `<Validation description> failed` and missing topics cause
`<Validation topics> failed: The repository has no valid topics`.

### 3. Add brand images

Create a `brand/` directory inside `custom_components/<domain>/` and add at
least `icon.png` (256×256 px, transparent background). See the
[HA brand image guide](https://developers.home-assistant.io/docs/creating_integration_file_structure#local-brand-images-for-custom-integrations)
for the full spec. Once the images are committed, remove the `ignore: brands`
line from `.github/workflows/validate.yml` so the HACS validation job enforces
the check going forward.

### 4. Run setup

```bash
scripts/setup
```

Creates `venv/`, installs dev deps from `requirements.txt`, and installs
pre-commit hooks.

## Hard rules

- **Write everything in English** — code, comments, docstrings, commit messages,
  PR descriptions, documentation.
- **Never edit `CHANGELOG.md` manually** — it is managed by `release-please`.
- **Never bump `version` in `manifest.json` manually** — `release-please` does it.
- **Never edit `.release-please-manifest.json`** — same reason.
- **Never edit `version.txt`** (appears in the repo root after the first
  release) — same reason.
- **Use Conventional Commits** (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`,
  `perf:`, `ci:`, `test:`). Bumps and changelog entries depend on the prefix:

  | Commit prefix | Version bump | Appears in changelog |
  | --- | --- | --- |
  | `feat: ...` | minor | Yes — **Features** |
  | `fix: ...` | patch | Yes — **Bug Fixes** |
  | `perf: ...` | patch | Yes — **Performance** |
  | `feat!: ...` or `BREAKING CHANGE:` in footer | major | Yes |
  | `refactor: ...` | none | Hidden |
  | `chore: ...` | none | Hidden |
  | `docs: ...` | none | Hidden |
  | `ci: ...` | none | Hidden |

  **First release — v1.0.0:** add `Release-As: 1.0.0` to the footer of any
  commit pushed to `main` before the first release. Release-please will
  accumulate all changes since the beginning and open a Release PR that
  produces exactly `v1.0.0`, regardless of which commit types were used:

  ```
  feat: implement sensor platform

  Release-As: 1.0.0
  ```
- **Ruff is pinned only in `.pre-commit-config.yaml`** — Dependabot's
  `pre-commit` ecosystem bumps it automatically. Do not add Ruff to
  `requirements.txt`; both `scripts/lint` and CI run it through pre-commit.
- **Do not commit secrets** or files under `config/` other than
  `config/configuration.yaml` (enforced by `.gitignore`).

## Project layout

```text
custom_components/<domain>/   # integration source
  __init__.py        # async_setup_entry / async_unload_entry — entry point
  api.py             # API client + typed exceptions
  config_flow.py     # UI config flow
  coordinator.py     # DataUpdateCoordinator
  const.py           # DOMAIN, LOGGER, attribution
  data.py            # runtime_data dataclass + typed ConfigEntry alias
  entity.py          # shared base entity
  binary_sensor.py / sensor.py / switch.py   # platform entities
  manifest.json      # HA integration metadata
  translations/      # UI strings (en.json is canonical)
config/              # HA dev config loaded by scripts/develop
scripts/             # lint / develop / setup wrappers
```

## Development workflow

### Shell

- `scripts/setup` — create `venv/` (recreates it on platform mismatch), install dev deps (`requirements.txt`), install pre-commit hooks
- `scripts/lint` — auto-calls `scripts/setup` if the venv is missing or invalid, then runs `pre-commit run --all-files` (same pipeline as CI)
- `scripts/develop` — auto-calls `scripts/setup` if the venv is missing or invalid, then starts Home Assistant on port 8123 with the integration loaded

### VS Code

Tasks are pre-configured in `.vscode/tasks.json`:

- **Run task → "Run Home Assistant"** — starts the dev server (calls `scripts/develop`).
- **Run task → "Lint"** — runs Ruff format + check with auto-fix (calls `scripts/lint`).
- **F5 → "Home Assistant"** — launches HA under the debugger; breakpoints work in `custom_components/`.

Do not duplicate task definitions; extend `.vscode/tasks.json` only if a new
common task is genuinely needed.

### Pre-commit hooks

Runs automatically before every `git commit`. To run manually:

```bash
pre-commit run --all-files              # all hooks
pre-commit run ruff-check --all-files   # single hook
```

| Hook | What it checks |
| --- | --- |
| `check-json` | `manifest.json`, `translations/*.json`, `hacs.json` |
| `check-yaml` | all `.yml` workflow and config files |
| `trailing-whitespace` | removes trailing spaces |
| `end-of-file-fixer` | ensures files end with a newline |
| `check-merge-conflict` | blocks accidental merge-conflict markers |
| `ruff-check` | lints Python and auto-fixes safe issues |
| `ruff-format` | formats Python code |
| `codespell` | catches common typos in code, comments and docs |

## Adding a new platform / entity type

1. Create `custom_components/<domain>/<platform>.py`.
2. Subclass the relevant HA entity (e.g. `SensorEntity`) and the shared
   `IntegrationBlueprintEntity` in `entity.py` for coordinator wiring.
3. Append the `Platform` enum value to the `PLATFORMS` list in `__init__.py`.
4. Add translation keys to `translations/en.json` if the entity is user-facing.

## Validation

CI runs three workflows on every push and PR (see `.github/workflows/`):

- **lint.yml** — the full pre-commit suite (`pre-commit run --all-files`) on
  Python 3.14 — the same pipeline as `scripts/lint`.
- **validate.yml** — `hassfest` (manifest, structure, translations) and HACS
  validation. Runs daily on cron too.
- **release-please.yml** — opens / updates the Release PR on `main`. Requires
  the repo setting *"Allow GitHub Actions to create and approve pull requests"*.

A change that touches `manifest.json`, `hacs.json`, or `translations/` will fail
fast if the JSON shape is wrong — fix locally with `pre-commit run --all-files`
before pushing.

## Python 3.14 syntax

The template targets Python 3.14 (`target-version = "py314"` in `.ruff.toml`). Do not flag 3.14-native syntax as an issue or suggest workarounds for older versions.

- **PEP 649 — lazy annotations**: forward references in annotations do not need to be quoted and `from __future__ import annotations` is not required. Names defined later in the module can be referenced in annotations without quoting.
- **`except TypeA, TypeB:`** without parentheses is valid Python 3.14 syntax.

## Ruff configuration

Defined in `.ruff.toml`, deliberately mirroring `home-assistant/core`
(`target-version = "py314"`, `select = ["ALL"]`, narrow `ignore` list). Do not
relax rules globally — prefer `# noqa: <code>` with a one-line justification
when a single line genuinely needs to break a rule.

## Dependencies

- `requirements.txt` is the single source of truth for dev / CI deps.
  Dependabot updates it weekly with grouped PRs (see `.github/dependabot.yml`).
- Hook versions in `.pre-commit-config.yaml` (including Ruff) are updated by
  Dependabot's `pre-commit` ecosystem — no manual bumping needed.
- `homeassistant` is **excluded** from Dependabot — it must stay in sync with
  the `homeassistant` key in `hacs.json`. Bump them together manually.
  When bumping the minimum HA version, update all three places in lockstep:
  `hacs.json → homeassistant`, `requirements.txt → homeassistant==`, and any
  minimum-version statement in `README.md` if one is present.

## Extension points

Lines starting with `# NOTE:` in the Python source mark places where the
template is deliberately minimal. Each note explains what is missing, when to
add it, and links to the relevant HA developer doc. Grep for `# NOTE:` before
asking the user where to extend — the answer is usually already inline.

## Keeping up with Home Assistant standards

Dependabot handles library and action bumps, but architectural alignment and
best practices should follow official Home Assistant documentation (both when
maintaining this template and after bootstrapping a custom component):

- **Developer Blog & Deprecations**: [developers.home-assistant.io/blog/](https://developers.home-assistant.io/blog/) —
  check monthly posts when bumping the minimum HA version for architectural
  changes, upcoming deprecations, and new helpers.
- **Developer Documentation**: [developers.home-assistant.io](https://developers.home-assistant.io/) —
  official reference for config flow, coordinator patterns, and entity platforms.
- **Integration Quality Scale**: [developers.home-assistant.io/docs/integration_quality_scale_index/](https://developers.home-assistant.io/docs/integration_quality_scale_index/) —
  best practices checklist (error handling, session management, translation keys).
- **Hassfest & HACS Action**: The CI workflow in `.github/workflows/validate.yml`
  runs `hassfest` from HA Core `master` and `hacs/action` daily to catch schema
  and manifest deprecations automatically.

## When in doubt

- Match patterns already in the repo before introducing new ones.
- Prefer editing existing files over creating new ones.
- Keep the template lightweight — every added file is friction for a first-time
  user. Only add what materially improves a common workflow.
