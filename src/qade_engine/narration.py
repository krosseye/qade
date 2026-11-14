# SPDX-License-Identifier: GPL-3.0-or-later
"""The intro narration: spoken aloud, or shown on timers without a voice."""

import logging
from time import perf_counter

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtTextToSpeech import QTextToSpeech, QVoice

_log = logging.getLogger(__name__)


class IntroSequencer(QObject):
    """Steps through the intro a line at a time, as each is spoken or timed out.

    Attributes:
        cycle_finished: Emitted after the last line. The intro restarts
            ``RESTART_DELAY_MS`` later unless stopped.
        RESTART_DELAY_MS: Pause before the intro repeats.
        SPEECH_START_TIMEOUT_MS: How long a voice has to start speaking a
            line before falling back to timers.
        lines: The narration, one line at a time.
        current_line: Index of the line being spoken, -1 before the first.
        line_start_times: When each shown line started, in ``perf_counter``
            seconds, for the typewriter effect.
        active: Whether the intro is running.
    """

    RESTART_DELAY_MS = 5000
    SPEECH_START_TIMEOUT_MS = 2000

    cycle_finished = Signal()

    def __init__(
        self,
        lines,
        use_tts=True,
        rate: float = 0.0,
        gender: QVoice.Gender | None = None,
    ):
        """Prepares the intro, silent until ``start``.

        Args:
            lines: The narration, one line at a time.
            use_tts: Speak it if the system has a voice; otherwise time it.
            rate: Speech speed, from -1 (slow) to 1 (fast).
            gender: Preferred voice. None takes the system's first.
        """
        super().__init__()
        self.lines = list(lines)
        self.current_line = -1
        self.line_start_times: dict[int, float] = {}
        self.active = False
        self._is_speaking = False

        self._advance_timer = QTimer(self)
        self._advance_timer.setSingleShot(True)
        self._advance_timer.timeout.connect(self._advance)
        self._restart_timer = QTimer(self)
        self._restart_timer.setSingleShot(True)
        self._restart_timer.timeout.connect(self._restart)
        self._start_check = QTimer(self)
        self._start_check.setSingleShot(True)
        self._start_check.setInterval(self.SPEECH_START_TIMEOUT_MS)
        self._start_check.timeout.connect(self._check_speech_started)

        self._speech = self._create_speech(rate, gender) if use_tts else None
        if use_tts and self._speech is None:
            _log.warning("text-to-speech unavailable: showing the intro on timers")

    @property
    def displayed_lines(self):
        """The lines reached so far, the current one included."""
        return self.lines[: self.current_line + 1]

    def start(self):
        """Starts the intro from its first line, unless already running."""
        if self.active:
            return
        self.active = True
        self._restart()

    def stop(self):
        """Stops the intro and any speech."""
        if not self.active:
            return
        self.active = False
        self._advance_timer.stop()
        self._restart_timer.stop()
        self._start_check.stop()
        # Cleared before stopping, so the state signal that follows is ignored.
        speaking, self._is_speaking = self._is_speaking, False
        if speaking and self._speech is not None:
            self._speech.stop()

    def _create_speech(self, rate: float, gender: QVoice.Gender | None):
        speech = QTextToSpeech()
        voices = speech.availableVoices()
        if not voices:
            return None
        speech.setVoice(next((v for v in voices if v.gender() == gender), voices[0]))
        speech.setRate(rate)
        speech.stateChanged.connect(self._on_speech_state_changed)
        return speech

    def _on_speech_state_changed(self, state):
        if state == QTextToSpeech.State.Error:
            self._give_up_speech()
        elif self.active and self._is_speaking and state == QTextToSpeech.State.Ready:
            self._advance()

    def _check_speech_started(self):
        # A voice that never starts (e.g. Wine lists SAPI voices it can't speak).
        speaking = (QTextToSpeech.State.Speaking, QTextToSpeech.State.Synthesizing)
        if self._is_speaking and self._speech and self._speech.state() not in speaking:
            self._give_up_speech()

    def _give_up_speech(self):
        if self._speech is None:
            return
        _log.warning(
            "text-to-speech failed (%s): showing the intro on timers",
            self._speech.errorString() or "never started speaking",
        )
        speech, self._speech = self._speech, None
        speech.stateChanged.disconnect(self._on_speech_state_changed)
        speech.stop()
        # This can run inside the object's own signal, so it must outlive this call.
        speech.setParent(self)
        speech.deleteLater()
        if self.active and self._is_speaking:
            self._is_speaking = False
            self._time_line(self.lines[self.current_line])

    def _time_line(self, text):
        base_delay = 2500 if self.current_line == 0 else 1000
        self._advance_timer.start(base_delay + len(text) * 50)

    def _restart(self):
        self.current_line = -1
        self._is_speaking = False
        self.line_start_times.clear()
        self._advance()

    def _advance(self):
        self._is_speaking = False
        self.current_line += 1

        if self.current_line >= len(self.lines):
            self._restart_timer.start(self.RESTART_DELAY_MS)
            self.cycle_finished.emit()
            return

        text = self.lines[self.current_line]
        self.line_start_times[self.current_line] = perf_counter()

        if self._speech is not None:
            self._is_speaking = True
            self._start_check.start()
            self._speech.say(text)
        else:
            self._time_line(text)
