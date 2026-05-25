"""A small, dependency-free CLI spinner for long-running searches.

Renders a 3-line ASCII orbit (a satellite emoji walking a clock-face path
around a stationary planet) on stderr in a background thread. No-ops in
non-TTY environments (CI, piped output) so it never corrupts captured
streams.
"""

from __future__ import annotations

import sys
import threading
from types import TracebackType

_EARTH = "🌍"
_SAT = "🛰️"
# Eight (row, col) positions around the earth at the centre of a 3x9 grid,
# walked clockwise starting at the top.
_POSITIONS: tuple[tuple[int, int], ...] = (
    (0, 4),  # N
    (0, 6),  # NE
    (1, 7),  # E
    (2, 6),  # SE
    (2, 4),  # S
    (2, 2),  # SW
    (1, 1),  # W
    (0, 2),  # NW
)
_ROWS = 3
_COLS = 9
_EARTH_POS = (1, 4)


class OrbitSpinner:
    """Context manager that animates a satellite orbiting an earth on stderr.

    Usage::

        with OrbitSpinner("Searching Umbra archive"):
            slow_work()

    Lines drawn::

           🛰️
          🌍
                 Searching Umbra archive…

    Safe in non-interactive environments: if stderr is not a TTY the
    animation is suppressed entirely (no escape codes are written).
    """

    def __init__(self, label: str = "Working", interval: float = 0.15) -> None:
        self.label = label
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False

    def __enter__(self) -> OrbitSpinner:
        if not sys.stderr.isatty():
            return self
        # Reserve four lines (three for the grid, one for the label).
        sys.stderr.write("\n" * (_ROWS + 1))
        sys.stderr.flush()
        self._active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()

    def stop(self) -> None:
        """Stop the animation and clear its frame."""
        if not self._active:
            return
        self._active = False
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None
        # Move cursor up over the reserved lines and clear each.
        n = _ROWS + 1
        sys.stderr.write(f"\033[{n}A")
        for _ in range(n):
            sys.stderr.write("\033[2K\n")
        sys.stderr.write(f"\033[{n}A")
        sys.stderr.flush()

    def _run(self) -> None:
        idx = 0
        while not self._stop.is_set():
            self._draw(idx)
            idx = (idx + 1) % len(_POSITIONS)
            self._stop.wait(self.interval)

    def _draw(self, idx: int) -> None:
        sat_r, sat_c = _POSITIONS[idx]
        # Each cell is one character; the earth/satellite glyphs render
        # double-width in most terminals, so we pad to keep alignment.
        grid = [[" " for _ in range(_COLS)] for _ in range(_ROWS)]
        er, ec = _EARTH_POS
        grid[er][ec] = _EARTH
        grid[sat_r][sat_c] = _SAT
        n = _ROWS + 1
        out = [f"\033[{n}A"]
        for row in grid:
            out.append("\033[2K  " + "".join(row) + "\n")
        out.append(f"\033[2K  {self.label}…\n")
        sys.stderr.write("".join(out))
        sys.stderr.flush()
