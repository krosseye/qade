# qade

A retro vector arcade game engine built on PySide6.

## Building from source

Run `uv run build.py` to build for your current platform.

`build.py` builds the launcher, with every game it lists, by default. Pass a game's package to build that game on its own:

```sh
uv run build.py grizzly_depths
```

## Command-line Arguments

- `--fullscreen`: Launch the game in fullscreen mode.
- `--no-music`: Launch the game without music.
- `--no-sfx`: Launch the game without sound effects.
- `--no-tts`: Launch the game without the text-to-speech intro.
- `--software-renderer`: Launch the game in software rendering mode.
