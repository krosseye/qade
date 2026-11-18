# Getting started

This page builds a small but complete game: a paddle slides along the bottom
of the screen while blocks fall from above. The engine supplies everything
around the gameplay: the standby and intro screens, pausing, the score and
saved high score, the HUD, the game-over screen and the fades between them.

## Lay out the package

A game is a Python package. The engine finds the game's files (e.g., the window
icon) in a `resources` folder inside it.

```text
dodge/
├── __init__.py    # the game's identity, and how to build it
├── __main__.py    # lets `python -m dodge` play it
├── game.py        # the game itself
└── resources/     # optional: icon.png
```

## Describe the game

`__init__.py` exports a [`GameDefinition`][qade_engine.host.GameDefinition]:
the game's [`GameInfo`][qade_engine.host.GameInfo], and a function that builds
it.

```python title="dodge/__init__.py"
--8<-- "examples/dodge/__init__.py"
```

```python title="dodge/__main__.py"
--8<-- "examples/dodge/__main__.py"
```

## Write the game

Subclass [`ArcadeGame`][qade_engine.arcade.ArcadeGame]. Set the class
attributes you need, and fill in the hooks:

- `build_input_map` names your controls.
- `reset` starts a fresh run.
- `step_playing` advances one fixed step of play. Read input from
  [`self.actions`][qade_engine.input.ActionState], and call `died()` to end
  the run.
- `draw_world` draws the play field.

```python title="dodge/game.py"
--8<-- "examples/dodge/game.py"
```

## Play it

```sh
python -m dodge
```

Press any key to go from the standby screen to the intro, and again to play.
Press `P` to pause and `Esc` to quit. A gamepad works too.

## Next steps

- **Sound effects:** override `register_sounds` and register sounds from
  [`presets`][qade_engine.audio.presets] or your own
  [`Sfx`][qade_engine.audio.Sfx]. Play them with `play_sound`.
- **Music:** write a [`Song`][qade_engine.audio.Song] for the sound chip and
  set `MUSIC` to it. It is baked the first time the game starts.
- **Smooth motion:** steps run at a fixed rate (`TICK_HZ`), not the display's.
  Move things on by [`frame.alpha`][qade_engine.host.Frame] of a step when
  drawing, so motion stays smooth on fast displays.
- **Fill the window:** set `FILL_WINDOW = True` and implement
  `field_resized`. The play field then takes the window's shape.
- **Effects:** `ArcadeGame` has a
  [`ParticleSystem`][qade_engine.graphics.ParticleSystem] as `self.particles`.
  During play, emit bursts from it and call `self.particles.update(dt)` in
  `step_playing`; draw it with `self.particles.draw(frame.painter)` in
  `draw_world`.
- **Moving stars:** during play the background only moves if you call
  [`self.starfield.scroll`][qade_engine.graphics.StarField] in `step_playing`.
- **Your own HUD readouts:** override `hud_rows`.

The [`ArcadeGame` reference](reference/arcade/arcade_game.md) lists every
setting and hook.
