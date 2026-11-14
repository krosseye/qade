# SPDX-License-Identifier: GPL-3.0-or-later
"""The standard arcade game that most QADE games are built on."""

import logging
from dataclasses import replace
from enum import Enum, auto

from PySide6.QtCore import Qt
from PySide6.QtTextToSpeech import QVoice

from qade_engine.audio import SoundBus, open_bus
from qade_engine.audio.music import MusicLoop
from qade_engine.core.field import PlayField
from qade_engine.core.state_machine import (
    Edge,
    StateMachine,
    Transition,
    TransitionStyle,
)
from qade_engine.graphics.particles import ParticleSystem
from qade_engine.graphics.starfield import StarField
from qade_engine.graphics.theme import current_theme
from qade_engine.graphics.transitions import draw_transition
from qade_engine.graphics.viewport import Viewport
from qade_engine.host.app import Frame, GameInfo, Services
from qade_engine.input import InputMap, UIAction, add_ui_actions
from qade_engine.narration import IntroSequencer
from qade_engine.persistence import HighScoreStore
from qade_engine.resources import resource_path
from qade_engine.ui.hud import draw_game_over, draw_hud, draw_paused, format_clock
from qade_engine.ui.overlays import draw_intro, draw_standby
from qade_engine.ui.panels import HudRow

_log = logging.getLogger(__name__)


class Phase(Enum):
    """The screens an ``ArcadeGame`` moves between.

    Attributes:
        STANDBY: The silent "incoming transmission" screen.
        INTRO: The narrated briefing, with music.
        PLAYING: A run in progress.
        PAUSED: A run held still. ``draw_world`` still draws it.
        GAME_OVER: The world keeps drifting, but nothing can score or collide.
    """

    STANDBY = auto()
    INTRO = auto()
    PLAYING = auto()
    PAUSED = auto()
    GAME_OVER = auto()


class Event(Enum):
    """What can change the phase, through ``ArcadeGame.send``.

    Attributes:
        CONFIRM: The player pressed a "press any key" key.
        PAUSE: Pause or resume a run.
        DIED: The player's run ended.
        INTRO_FINISHED: The narration reached its last line.
        TIMEOUT: Sent by the state machine when a phase times out.
    """

    CONFIRM = auto()
    PAUSE = auto()
    DIED = auto()
    INTRO_FINISHED = auto()
    TIMEOUT = auto()


class ArcadeGame:
    """Base class for standard arcade games. Implements the host's ``App``.

    It supplies the flow STANDBY -> INTRO -> PLAYING -> GAME_OVER with fades,
    pausing, score and a saved high score, a starfield, particles, music,
    sound effects, the spoken intro and the standard screens. A game subclasses
    it, overrides the class attributes it needs, and implements the hooks:
    ``build_input_map``, ``setup``, ``reset``, ``step_playing``,
    ``step_aftermath``, ``step_idle``, ``field_resized``, ``register_sounds``,
    ``draw_world`` and ``hud_rows``.

    Update contract:

    * ``step(dt)`` is the only entry point that advances time. The host calls
      it once per fixed step of ``1 / TICK_HZ``, in every phase.
    * A step never reads the wall clock or input devices directly. Input is
      read from ``actions``, which only changes between steps.
    * The phase only changes through ``send(event)`` and ``flow_table``.
      Events from outside (input, the intro) arrive between steps. Timeouts
      and transitions play out inside steps, on simulation time.
    * ``draw`` reads state and never modifies it.

    Attributes:
        INFO: The game's identity. Required.
        CANVAS_SIZE: Logical resolution; the host scales it to fit the window.
        MUSIC: Music file in the game package's ``resources`` folder, or None.
        MUSIC_VOLUME: Music volume, 0 to 1.
        TRANSMISSION_TITLE: Header of the standby and intro screens. Empty
            uses the game's title.
        STANDBY_MESSAGE: Message on the standby screen.
        STANDBY_PROMPT: Prompt on the standby screen.
        INTRO_LINES: The intro narration, one line at a time.
        INTRO_HIGHLIGHTS: Intro lines containing any of these are drawn red.
        INTRO_PROMPT: Prompt on the intro screen.
        GAME_OVER_TITLE: Title of the game-over screen.
        GAME_OVER_PROMPT: Prompt on the game-over screen.
        PAUSED_TITLE: Title of the pause screen.
        PAUSED_PROMPT: Prompt on the pause screen.
        HUD_TITLE: Header of the HUD's game panel.
        VOICE_RATE: Narration speed, from -1 (slow) to 1 (fast).
        VOICE_GENDER: Preferred narrator voice. None takes any.
        NEVER_CONFIRM: Keys that never dismiss a "press any key" screen,
            typically steering, so a player still turning at death doesn't
            skip past the game-over screen.
        TICK_HZ: Fixed steps per second. A power of two keeps ``1 / TICK_HZ``
            exact in floating point.
        NUM_STARS: Stars in the background. 0 for none.
        STARS_IN_PLAY: False shows stars only behind the standby and intro
            screens.
        FILL_WINDOW: True makes ``field`` take the window's shape, and calls
            ``field_resized`` when it changes during a run.
        IDLE_STAR_VELOCITY: Star drift outside play, in px/s.
        GAME_OVER_IDLE_TIMEOUT: Seconds on the game-over screen before
            falling back to standby.
        GAME_OVER_DELAY: Seconds the death plays out before the game-over
            panel appears and a key can dismiss it.
        INTRO_LOOPS_BEFORE_STANDBY: Full narrations before the intro falls
            back to standby.
        STANDBY_FADE_TIME: Seconds of each fade back to standby.
        GAMEPLAY_FADE_TIME: Seconds of each fade into and between runs.
        services: What the host provides.
        actions: Held input, for steps to read.
        field: The play area, in canvas units.
        particles: Visual-only particles, stepped with the simulation.
        starfield: The background stars, rebuilt for each run.
        sounds: The sound bus, or None when sound effects are off or headless.
        score: This run's score.
        elapsed: Seconds of play this run.
        high_score: The best score so far.
        is_new_high_score: Whether this run set the high score.
        tick_count: Fixed steps executed since creation.
    """

    INFO: GameInfo
    CANVAS_SIZE: tuple[int, int] = (800, 600)
    MUSIC: str | None = None
    MUSIC_VOLUME = 0.25

    TRANSMISSION_TITLE = ""
    STANDBY_MESSAGE = "READY"
    STANDBY_PROMPT = "[ PRESS ANY KEY ]"
    INTRO_LINES: tuple[str, ...] = ()
    INTRO_HIGHLIGHTS: tuple[str, ...] = ()
    INTRO_PROMPT = "[ PRESS ANY KEY TO START ]"
    GAME_OVER_TITLE = "GAME OVER"
    GAME_OVER_PROMPT = "[ PRESS ANY KEY TO PLAY AGAIN ]"
    PAUSED_TITLE = "PAUSED"
    PAUSED_PROMPT = "[ PRESS P OR START TO RESUME ]"
    HUD_TITLE = "PLAYER"
    VOICE_RATE = 0.0
    VOICE_GENDER: QVoice.Gender | None = None

    NEVER_CONFIRM: tuple[Qt.Key, ...] = ()
    TICK_HZ = 64
    NUM_STARS = 200
    STARS_IN_PLAY = True
    FILL_WINDOW = False
    IDLE_STAR_VELOCITY: tuple[float, float] = (0.0, -480.0)
    GAME_OVER_IDLE_TIMEOUT = 30.0
    GAME_OVER_DELAY = 0.0
    INTRO_LOOPS_BEFORE_STANDBY = 3
    STANDBY_FADE_TIME = 2.0
    GAMEPLAY_FADE_TIME = 1.0

    def __init__(
        self, services: Services, high_score_store: HighScoreStore | None = None
    ):
        """Builds the game. Audio and the intro are acquired later, in ``start``.

        Args:
            services: What the host provides.
            high_score_store: Where the high score is kept. Defaults to the
                game's standard save location.
        """
        self.services = services
        self.actions = services.actions
        self.canvas_size = self.CANVAS_SIZE
        self.tick_hz = self.TICK_HZ
        self.dt = 1.0 / self.TICK_HZ
        self.input_map = add_ui_actions(
            self.build_input_map(), never_confirm=self.NEVER_CONFIRM
        )
        self.tick_count = 0

        self.high_score_store = high_score_store or HighScoreStore.for_game(
            self.INFO.id
        )
        self.high_score = self.high_score_store.load()

        self._music: MusicLoop | None = None
        self.sounds: SoundBus | None = None
        self._intro: IntroSequencer | None = None
        self._suspended = False

        self.field = PlayField(*self.CANVAS_SIZE)
        self.particles = ParticleSystem()
        self.flow = StateMachine(
            Phase.STANDBY,
            self.flow_table(),
            timeout_event=Event.TIMEOUT,
            timeouts={Phase.GAME_OVER: self.GAME_OVER_IDLE_TIMEOUT},
            on_change=self._on_phase_change,
        )
        # Last, so the hooks see a fully built game.
        self.setup()
        self._new_run()

    def build_input_map(self) -> InputMap:
        """Hook: the game's own actions.

        Confirm, quit, pause and the performance toggle are added afterwards.

        Returns:
            The game's input map.
        """
        return InputMap()

    def setup(self) -> None:
        """Hook: create long-lived systems. Called once, before the first ``reset``."""

    def reset(self) -> None:
        """Hook: start a fresh run, such as the ship, enemies and per-run counters."""

    def step_playing(self, dt: float) -> None:
        """Hook: one fixed step of gameplay. Call ``died`` to end the run.

        Args:
            dt: Step length in seconds.
        """

    def step_aftermath(self, dt: float) -> None:
        """Hook: one fixed step after death. By default stars drift and particles finish.

        Args:
            dt: Step length in seconds.
        """
        self.starfield.scroll(*self.IDLE_STAR_VELOCITY, dt)
        self.particles.update(dt)

    def step_idle(self, dt: float) -> None:
        """Hook: one fixed step on the standby and intro screens. By default stars drift.

        Args:
            dt: Step length in seconds.
        """
        self.starfield.scroll(*self.IDLE_STAR_VELOCITY, dt)

    def field_resized(self, grew_x: float, grew_y: float) -> None:
        """Hook: a ``FILL_WINDOW`` game's field changed shape during a run.

        Move the world to suit. On the standby and intro screens ``reset`` is
        called instead.

        Args:
            grew_x: How much wider the field became, in canvas units.
            grew_y: How much taller the field became, in canvas units.
        """

    def register_sounds(self, bus: SoundBus) -> None:
        """Hook: register the game's sound effects. Called on start.

        Args:
            bus: The bus to call ``register`` on.
        """

    def draw_world(self, frame: Frame) -> None:
        """Hook: draw the play field over the stars.

        Called while PLAYING, PAUSED and GAME_OVER, never on the standby or
        intro screens. Draw the player unless ``phase is Phase.GAME_OVER``.

        Args:
            frame: What to draw with.
        """

    def hud_rows(self) -> list[HudRow]:
        """Hook: readouts for the HUD's game panel.

        Returns:
            The rows to show. By default score, best and time.
        """
        theme = current_theme()
        return [
            HudRow("SCORE", f"{self.score:06d}", theme.accent),
            HudRow("BEST", f"{self.high_score:06d}", theme.highlight),
            HudRow("TIME", format_clock(self.elapsed), theme.text),
        ]

    def flow_table(self) -> dict[tuple[Phase, Event], Edge[Phase]]:
        """Every legal phase change. An event with no entry is ignored.

        Returns:
            The edges, keyed by (phase, event).
        """

        def fade(target: Phase, duration: float, times: int = 1) -> Edge[Phase]:
            return Edge(
                target, times=times, style=TransitionStyle.FADE, duration=duration
            )

        play, back = self.GAMEPLAY_FADE_TIME, self.STANDBY_FADE_TIME
        return {
            (Phase.STANDBY, Event.CONFIRM): fade(Phase.INTRO, play),
            (Phase.INTRO, Event.CONFIRM): fade(Phase.PLAYING, play),
            (Phase.INTRO, Event.INTRO_FINISHED): fade(
                Phase.STANDBY, back, times=self.INTRO_LOOPS_BEFORE_STANDBY
            ),
            # A hard cut: a fade would keep PLAYING running (and the player
            # hittable) until its halfway switch, and darken the death effect.
            (Phase.PLAYING, Event.DIED): Edge(Phase.GAME_OVER),
            (Phase.PLAYING, Event.PAUSE): Edge(Phase.PAUSED),
            (Phase.PAUSED, Event.PAUSE): Edge(Phase.PLAYING),
            (Phase.GAME_OVER, Event.CONFIRM): fade(Phase.PLAYING, play),
            (Phase.GAME_OVER, Event.TIMEOUT): fade(Phase.STANDBY, back),
        }

    @property
    def phase(self) -> Phase:
        """The current phase."""
        return self.flow.state

    @property
    def transition(self) -> Transition[Phase] | None:
        """The phase change currently playing, if any."""
        return self.flow.transition

    def send(self, event: Event) -> bool:
        """Reports something that happened.

        Args:
            event: What happened.

        Returns:
            True if it starts a change of phase.
        """
        return self.flow.send(event)

    def died(self) -> None:
        """Ends the current run."""
        self.send(Event.DIED)

    def _on_phase_change(self, source: Phase, target: Phase):
        if target is not Phase.PLAYING and self.sounds is not None:
            self.sounds.stop_loops()
        if target is Phase.GAME_OVER:
            self._record_high_score()
        if source is Phase.GAME_OVER:
            self._new_run()

    def _record_high_score(self):
        if self.score > self.high_score:
            self.high_score = self.score
            self.is_new_high_score = True
            self.high_score_store.save(self.high_score)

    def _new_run(self):
        width, height = self.CANVAS_SIZE
        self.starfield = StarField(width, height, self.NUM_STARS)
        self.particles.clear()
        self.score = 0
        self.is_new_high_score = False
        self.elapsed = 0.0
        self.reset()

    def start(self) -> None:
        """Acquires music, the intro and sound effects, as the settings allow."""
        if self.MUSIC and self.services.settings.music:
            path = resource_path(self.INFO.package, self.MUSIC)
            if path.exists():
                self._music = MusicLoop(path, volume=self.MUSIC_VOLUME)
            else:
                _log.warning("music not found, playing without it: %s", path)
        self._intro = IntroSequencer(
            self.INTRO_LINES,
            use_tts=self.services.settings.use_tts,
            rate=self.VOICE_RATE,
            gender=self.VOICE_GENDER,
        )
        self._intro.cycle_finished.connect(lambda: self.send(Event.INTRO_FINISHED))
        if self.services.settings.sound_effects:
            self.sounds = open_bus(self.register_sounds)
        self._sync_presentation()

    def stop(self) -> None:
        """Releases everything ``start`` acquired.

        A run left early still counts towards the high score.
        """
        if self.phase in (Phase.PLAYING, Phase.PAUSED):
            self._record_high_score()
        if self._music is not None:
            self._music.stop()
        if self._intro is not None:
            self._intro.stop()
        if self.sounds is not None:
            self.sounds.close()
        self._music = self._intro = self.sounds = None

    def suspend(self) -> None:
        """The player went away: pauses a run, and goes quiet whatever the phase."""
        self._suspended = True
        if self.phase is Phase.PLAYING:
            self.send(Event.PAUSE)
        self._sync_presentation()

    def resume(self) -> None:
        """The player is back. A paused run stays paused until they resume it."""
        self._suspended = False
        self._sync_presentation()

    def play_sound(self, name: str, step: int | None = None, vol: float = 1.0) -> None:
        """Plays a registered sound. Does nothing when sound effects are off.

        Args:
            name: The registered sound.
            step: Which pitch to play, for a sound registered with ``semitones``.
            vol: Volume, 0 to 1.
        """
        if self.sounds is not None:
            self.sounds.play(name, step=step, vol=vol)

    def stop_sound(self, name: str) -> None:
        """Stops every voice of a registered sound.

        Args:
            name: The registered sound.
        """
        if self.sounds is not None:
            self.sounds.stop(name)

    def on_action(self, action: str) -> None:
        """Handles a one-shot UI action.

        Args:
            action: The action that was pressed.
        """
        if action == UIAction.CONFIRM and not self._game_over_pending():
            self.send(Event.CONFIRM)
        elif action == UIAction.PAUSE:
            self.send(Event.PAUSE)

    def _game_over_pending(self) -> bool:
        """True while a death plays out, before the game-over panel appears."""
        return (
            self.phase is Phase.GAME_OVER
            and self.flow.time_in_state < self.GAME_OVER_DELAY
        )

    def _fit_field(self) -> None:
        window = self.services.window_size
        if not self.FILL_WINDOW or window is None:
            return
        view = Viewport.fit(window, self.CANVAS_SIZE)
        grew_x, grew_y = view.width - self.field.width, view.height - self.field.height
        if not (grew_x or grew_y):
            return
        self.field.width, self.field.height = view.width, view.height
        if self.phase in (Phase.STANDBY, Phase.INTRO):
            self.reset()
        else:
            self.field_resized(grew_x, grew_y)

    def step(self, dt: float) -> None:
        """Advances one fixed step, then syncs music and narration to the phase.

        Args:
            dt: Step length in seconds.
        """
        self._fit_field()
        self.tick_count += 1
        self.flow.advance(dt)
        match self.phase:
            case Phase.PLAYING:
                self.elapsed += dt
                self.step_playing(dt)
            case Phase.GAME_OVER:
                self.step_aftermath(dt)
            case Phase.STANDBY | Phase.INTRO:
                self.step_idle(dt)
            case Phase.PAUSED:
                pass
        self._sync_presentation()

    def _sync_presentation(self) -> None:
        """Starts or stops music and the intro to suit the phase.

        Music plays everywhere but standby and pause; the intro runs only
        while it shows. Both are silent while the player is away.
        """
        phase = self.phase
        if self._music is not None:
            if self._suspended or phase in (Phase.STANDBY, Phase.PAUSED):
                self._music.stop()
            else:
                self._music.start()
        if self._intro is not None:
            if phase is Phase.INTRO and not self._suspended:
                self._intro.start()
            else:
                self._intro.stop()

    def draw(self, frame: Frame) -> None:
        """Draws the current phase: its screen, or the world and HUD.

        Args:
            frame: What to draw with.
        """
        if self.phase is Phase.PAUSED:
            frame = replace(frame, alpha=1.0)
        painter, view = frame.painter, frame.view
        if self.STARS_IN_PLAY or self.phase in (Phase.STANDBY, Phase.INTRO):
            self.starfield.draw(painter, view.width, view.height, frame.alpha * self.dt)
        title = self.TRANSMISSION_TITLE or self.INFO.title.upper()

        match self.phase:
            case Phase.STANDBY:
                draw_standby(
                    painter,
                    view,
                    frame.now,
                    title,
                    self.STANDBY_MESSAGE,
                    self.STANDBY_PROMPT,
                )
            case Phase.INTRO:
                if self._intro is not None:
                    draw_intro(
                        painter,
                        view,
                        self._intro,
                        frame.now,
                        title,
                        self.INTRO_PROMPT,
                        self.INTRO_HIGHLIGHTS,
                    )
            case _:
                self.draw_world(frame)
                draw_hud(painter, view, self.hud_rows(), frame.perf, self.HUD_TITLE)
                if self.phase is Phase.PAUSED:
                    draw_paused(painter, view, self.PAUSED_TITLE, self.PAUSED_PROMPT)
                elif self.phase is Phase.GAME_OVER and not self._game_over_pending():
                    draw_game_over(
                        painter,
                        view,
                        self.GAME_OVER_TITLE,
                        self.GAME_OVER_PROMPT,
                        self.score,
                        self.high_score,
                        self.is_new_high_score,
                    )

        if self.transition is not None:
            draw_transition(painter, view.width, view.height, self.transition)
