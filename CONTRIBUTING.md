# Contributing to Desktop Pet

Thanks for considering a contribution! This project is built incrementally,
phase by phase (see the Roadmap in the README) — please check which phase is
currently active before opening a large PR, so your work lands on the right
foundation.

## Getting set up

```bash
git clone https://github.com/your-org/desktop-pet.git
cd desktop-pet
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Before opening a PR

1. **Run the tests:** `pytest`
2. **Run the linter:** `ruff check src tests`
3. **Follow the architecture rules** in
   [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — most importantly:
   subsystems talk to each other only through the event bus, never by
   importing each other's internals.
4. **Add or update tests** for any behavior change.
5. **Add a docstring** to every new public class and function.

## Adding a new pet (no code required!)

Once the plugin system lands (Phase 8), new pets are just a folder under
`pets/` or `plugins/` containing:

```
your-pet/
├── sprites/
├── config.json
├── animations.json
├── sounds/
└── personality.json
```

No Python required — see the plugin docs (added in Phase 8) for the schema.

## Commit style

Use clear, present-tense commit messages, e.g. `Add gravity to physics engine`
rather than `Added stuff`. Reference the phase or issue number where useful.

## Code of conduct

Be respectful and constructive. This is a hobby/community project and
everyone's time is valuable.
