"""Hold the last confirmed scoreboard state across abstentions and show how fresh it is (F-4).

The scoreboard reader abstains (``None``) whenever the bug is hidden by a graphic, a replay or
another camera. A display must not go blank or invent values at those moments, so this tracker
keeps, per field, the last value a reader confirmed together with the playback second it was
confirmed at. Every output carries ``age_seconds`` (now minus last confirmation) and a
``stale`` flag once the age exceeds ``stale_after_seconds``; consumers decide what to show.

Rules (deliberately simple, no game logic):

* a non-null reading replaces the held value and resets its age;
* a null reading keeps the held value and lets the age grow;
* a reading that is impossible for the field (balls > 3, strikes > 2, outs > 2, inning < 1,
  negative scores, unknown half) is ignored and counted under ``rejected``;
* a change a scoreboard cannot make between two confirmed snapshots (the inning going
  backwards, a score going down) is still accepted, because the earlier reading might have
  been the wrong one, but it is recorded under ``suspect`` with both snapshots so the UI can
  flag it. No other game logic is applied.

The tracker never guesses a value it has not seen and never converts feed UTC to seconds.
"""

FIELDS = (
    "balls",
    "strikes",
    "outs",
    "runner_on_1b",
    "runner_on_2b",
    "runner_on_3b",
    "inning",
    "inning_topbot",
    "home_score",
    "away_score",
)
LIMITS = {"balls": (0, 3), "strikes": (0, 2), "outs": (0, 2), "inning": (1, 30)}


def _valid(name, value):
    if name in LIMITS:
        low, high = LIMITS[name]
        return type(value) is int and low <= value <= high
    if name in ("home_score", "away_score"):
        return type(value) is int and value >= 0
    if name == "inning_topbot":
        return value in ("Top", "Bot")
    return type(value) is bool


def _suspect(previous, current):
    """Transitions between two confirmed snapshots that a scoreboard cannot make."""
    reasons = []
    if previous["inning"] is not None and current["inning"] is not None:
        if current["inning"] < previous["inning"]:
            reasons.append("inning_decreased")
    for name in ("home_score", "away_score"):
        if (
            previous[name] is not None
            and current[name] is not None
            and current[name] < previous[name]
        ):
            reasons.append(f"{name}_decreased")
    return reasons


class ScoreboardTracker:
    def __init__(self, stale_after_seconds=10.0):
        self.stale_after_seconds = float(stale_after_seconds)
        self.values = dict.fromkeys(FIELDS)
        self.confirmed_at = dict.fromkeys(FIELDS)
        self.last_seconds = None
        self.rejected = []
        self.suspect = []

    def update(self, seconds, reading):
        """Feed one reading (field -> value or None) taken at playback ``seconds``."""
        seconds = float(seconds)
        if self.last_seconds is not None and seconds < self.last_seconds:
            raise ValueError("Readings must arrive in playback order")
        before = dict(self.values)
        for name in FIELDS:
            value = reading.get(name)
            if value is None:
                continue
            if not _valid(name, value):
                self.rejected.append({"seconds": seconds, "field": name, "value": value})
                continue
            self.values[name] = value
            self.confirmed_at[name] = seconds
        for reason in _suspect(before, self.values):
            self.suspect.append(
                {"seconds": seconds, "reason": reason, "before": before, "after": dict(self.values)}
            )
        self.last_seconds = seconds
        return self.state(seconds)

    def state(self, seconds):
        """The held state at playback ``seconds`` with per-field freshness."""
        seconds = float(seconds)
        out = {}
        for name in FIELDS:
            confirmed = self.confirmed_at[name]
            age = None if confirmed is None else round(seconds - confirmed, 3)
            out[name] = {
                "value": self.values[name],
                "confirmed_at": confirmed,
                "age_seconds": age,
                "stale": age is None or age > self.stale_after_seconds,
            }
        return {
            "seconds": seconds,
            "fields": out,
            "any_confirmed": any(v is not None for v in self.values.values()),
            "all_fresh": all(not f["stale"] for f in out.values()),
        }


def track_sequence(readings, stale_after_seconds=10.0):
    """Run the tracker over ``[(seconds, reading), ...]`` and return every state plus the log."""
    tracker = ScoreboardTracker(stale_after_seconds)
    states = [
        tracker.update(seconds, reading)
        for seconds, reading in sorted(readings, key=lambda r: r[0])
    ]
    return {"states": states, "rejected": tracker.rejected, "suspect": tracker.suspect}
