# 🐾 Desktop Pet

A free, open-source, physics-based virtual desktop companion — built to feel
like a real pet, not an animated GIF stuck on your screen.

Walks, sleeps, jumps, reacts to your cursor, gets curious, gets bored, gets
excited — driven by a real behavior engine and real physics, not random
jitter.

> **Status:** 🚧 Early development (Phase 1 of 10 — project scaffolding).
> There is no pet on your screen yet! See [Roadmap](#roadmap) below.

## Why this project?

Most "desktop pet" apps are a looping GIF with drag-to-move. This one is
built like real software:

- A **behavior engine** (finite state machine) instead of `random.choice()`
- **Real physics** — gravity, velocity, friction, bounce, collision
- A **plugin system** so anyone can add a new pet with zero code —
  just sprites + JSON
- **100% free and open-source** dependencies, MIT-licensed, safe for
  commercial use

## Requirements

- Python 3.11+
- Windows, macOS, or Linux

## Installation

```bash
git clone https://github.com/your-org/desktop-pet.git
cd desktop-pet
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Running

```bash
python -m desktop_pet.main
```

This launches the pet: a transparent, frameless, always-on-top window
showing the pet sprite, running its update loop at 60 FPS. Press
**Esc** (with the window focused) to quit.

### Using your own sprite

Drop a PNG at `assets/sprites/user_pet.png` and it will be used
automatically instead of the generated placeholder cat — no config or
code changes needed. (If you don't have one yet, run
`python scripts/generate_placeholder_asset.py` to (re)generate the
placeholder at `assets/sprites/placeholder_pet.png`.)

## Running the tests

```bash
pip install -e ".[dev]"
pytest
```

## Roadmap

| Phase | Milestone            | Status      |
|-------|-----------------------|-------------|
| 1     | Project setup          | ✅ Done     |
| 2     | Window system          | ✅ Done     |
| 3     | Animation engine       | ⬜ Planned  |
| 4     | Physics                | ⬜ Planned  |
| 5     | Cursor following       | ⬜ Planned  |
| 6     | Behavior engine        | ⬜ Planned  |
| 7     | Customization          | ⬜ Planned  |
| 8     | Plugin support         | ⬜ Planned  |
| 9     | Optimization           | ⬜ Planned  |
| 10    | Packaging & release    | ⬜ Planned  |

## Project layout

```
desktop-pet/
├── src/desktop_pet/   # Application source (see docs/ARCHITECTURE.md)
│   ├── core/          # Bootstrap, DI container, event bus, config
│   ├── physics/       # Gravity, velocity, collision
│   ├── animation/     # Sprite sheets, frame playback
│   ├── audio/         # Sound effects, ambient sound
│   ├── behavior/      # State machine / personality engine
│   └── ui/            # Transparent always-on-top window
├── pets/              # Built-in pet packs (sprites + config, no code)
├── plugins/           # Community pet packs go here
├── assets/            # Shared assets (icons, default sounds)
├── config/            # Default configuration
├── docs/              # Architecture & design docs
├── tests/             # Unit & integration tests
└── .github/           # CI workflows, issue/PR templates
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design.

## Contributing

Contributions are very welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

[MIT](LICENSE) — free for personal and commercial use.
