# Music

Games make their music on a sound chip: a [`Song`][qade_engine.audio.Song]
is written as text in Python, and baked into a WAV the first time it plays.
There are no audio files to ship.

This page builds up to a full song one idea at a time, then plays songs in a
game. The examples live in `examples/music`; hear them all with:

```sh
python -m examples.music songs
```

which bakes each one to a WAV file in `songs/`.

## Notes, holds and rests

A song has up to four parts, one per channel of the chip. A part is an
instrument and a pattern of steps. The instrument is an
[`Sfx`][qade_engine.audio.Sfx]: each note fills in its pitch and length.

```python title="examples/music/notes.py"
--8<-- "examples/music/notes.py"
```

## Chords

A channel plays one note at a time, so a chord is played as an arpeggio:
the chip cycles through its notes.

```python title="examples/music/chords.py"
--8<-- "examples/music/chords.py"
```

## Drums

A kit maps drum names to sounds. A part shorter than the song repeats to
fill it, so one bar of drums can run under a longer tune.

```python title="examples/music/drums.py"
--8<-- "examples/music/drums.py"
```

## A band

Patterns are plain strings, so ordinary Python builds the repetitive parts.

```python title="examples/music/band.py"
--8<-- "examples/music/band.py"
```

## Stings

A song with `loop=False` plays once and lets its last notes ring out: a
sting, for a level cleared or a game over.

```python title="examples/music/sting.py"
--8<-- "examples/music/sting.py"
```

## Playing music in a game

Set `MUSIC` on your game to the song it opens with. Each run starts with it,
and it plays in every phase but standby and pause.

```python
from examples.music import band, sting

class MyGame(ArcadeGame):
    MUSIC = band.SONG
```

Change track with `play_music`. One track plays at a time, apart from
sound effects:

- **A looping song** becomes the background music, replacing what was
  playing. Asking for the background that is already playing does nothing,
  so it is safe to call every step.
- **A one-shot** interrupts the background, then hands back to it when it
  ends. The background restarts from the top.
- **None** makes the background silence. Set it before a sting for a sting
  that ends in silence.

```python
def step_playing(self, dt):
    ...
    if self.level_cleared():
        self.play_music(sting.SONG)  # then back to the background
    if self.boss_arrived():
        self.play_music(BOSS_THEME)  # any looping Song: the new background
    if self.hit():
        self.play_music(None)  # nothing to hand back to,
        self.play_music(sting.SONG)  # so the sting ends in silence
        self.died()
```

A song is baked the first time it plays, which takes a moment for a long
one, and is kept in a cache after that. Music stays quiet when the player
turns it off; `play_music` is still safe to call.
