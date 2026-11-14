# App contract

Every game draws with a [`Frame`][qade_engine.host.Frame] and reaches the
host through [`Services`][qade_engine.host.Services]. In an `ArcadeGame` they
arrive as `draw_world(frame)` and `self.services`.

Implement [`App`][qade_engine.host.App] directly only for something that
isn't an arcade game, such as a launcher. Most games subclass
[`ArcadeGame`][qade_engine.arcade.ArcadeGame] instead, which implements it.

::: qade_engine.host.Frame

::: qade_engine.host.Services

::: qade_engine.host.App
