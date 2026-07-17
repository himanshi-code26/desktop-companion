# Architecture

Desktop Pet is built as a set of loosely-coupled subsystems that communicate
through a central **event bus**, rather than calling each other directly.
This is what keeps the codebase free of the "spaghetti code" that most
desktop-pet hobby projects turn into.

```
+-------------+     +-----------+     +-------------+
|   physics   | --> |           | --> |  animation  |
+-------------+     |           |     +-------------+
                     |  event    |
+-------------+     |   bus     |     +-------------+
|  behavior   | <-> |           | <-> |     ui      |
+-------------+     |           |     +-------------+
                     +-----------+
+-------------+           ^
|    audio    | <---------+
+-------------+
```

## Subsystems

| Package     | Responsibility                                                        |
|-------------|------------------------------------------------------------------------|
| `core`      | App bootstrap, dependency injection container, event bus, config loading |
| `physics`   | Gravity, velocity, acceleration, collision, edge/ground detection       |
| `animation` | Sprite sheet loading, frame playback, blending between animations       |
| `audio`     | Sound effect + ambient sound playback, volume/mute control              |
| `behavior`  | The pet's finite state machine (personality, transitions, cursor logic)|
| `ui`        | The transparent, frameless, always-on-top window and paint surface     |

## Design principles

1. **Single direction of dependency for domain logic.** `behavior` decides
   *what* the pet should do; it never touches Qt, sprite files, or audio
   devices directly. It emits events like `state_changed(Sleeping)` onto
   the event bus. `animation`, `audio`, and `ui` subscribe to those events
   and react — they don't ask `behavior` for anything.
2. **No subsystem imports another subsystem's internals.** Only `core`
   interfaces and the event bus are shared. This is enforced by code
   review and, eventually, a lint rule.
3. **Dependency Injection over globals.** The app's composition root
   (introduced in Phase 2) wires concrete implementations into the
   subsystems that need them, so each subsystem can be unit-tested with
   fakes/mocks instead of real Qt windows or audio devices.
4. **Delta-time everywhere.** All movement and animation timing is driven
   by elapsed frame time, never a fixed tick count, so behavior looks the
   same at 30 FPS and 144 FPS.
5. **Plugins are data, not code.** A community-made pet is a folder of
   sprites + JSON config — never a Python file that gets imported and
   executed. This is both a security boundary and what keeps the plugin
   system approachable for non-programmers.

## Status

This document will grow with each phase. As of Phase 1, only `core`'s
bootstrap logic (`desktop_pet.main`) exists; every other package is an
empty, importable stub reserved for its future phase.
