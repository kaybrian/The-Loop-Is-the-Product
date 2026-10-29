"""
DevFest Demo 1: A payment router that learns on its own.

Three simulated payment rails. Each has a hidden success rate the router
does not know. A fixed-rule router always uses the rail that was best at
launch. A Thompson-sampling router learns from every transaction.

Halfway through, the "best" rail degrades (an outage, a network issue,
a partner change). Watch which router notices.

Run:  python demo1_bandit_router.py
      python demo1_bandit_router.py --plot             (live chart, needs matplotlib)
      python demo1_bandit_router.py --plot --speed 10  (slower, for narrating)
"""
import argparse
import random
from collections import deque

RAILS = ["Rail A", "Rail B", "Rail C"]

# Hidden truth. The router never sees these numbers.
SUCCESS_RATES = {"Rail A": 0.92, "Rail B": 0.85, "Rail C": 0.78}
DRIFT_AT = 3000                      # transaction where the world changes
DRIFTED = {"Rail A": 0.60, "Rail B": 0.85, "Rail C": 0.88}
TOTAL = 6000


def true_rate(rail, t):
    return (DRIFTED if t >= DRIFT_AT else SUCCESS_RATES)[rail]


def send(rail, t, rng):
    """Simulate one transaction. Returns 1 for success, 0 for failure."""
    return 1 if rng.random() < true_rate(rail, t) else 0


class FixedRouter:
    """What most of us ship: pick the best rail once, hard-code it."""
    name = "Fixed rule"

    def choose(self, rng):
        return "Rail A"

    def learn(self, rail, reward):
        pass


class ThompsonRouter:
    """
    Keeps a belief (a Beta distribution) about each rail's success rate.
    For every transaction: sample a plausible rate from each belief,
    route to the highest sample, then update that belief with the result.
    `decay` slowly forgets old evidence so the router can notice change.
    """
    name = "Learning router"

    def __init__(self, decay=0.995):
        self.wins = {r: 1.0 for r in RAILS}
        self.losses = {r: 1.0 for r in RAILS}
        self.decay = decay

    def choose(self, rng):
        samples = {r: rng.betavariate(self.wins[r], self.losses[r]) for r in RAILS}
        return max(samples, key=samples.get)

    def learn(self, rail, reward):
        for r in RAILS:                      # forget a little, everywhere
            self.wins[r] = 1 + (self.wins[r] - 1) * self.decay
            self.losses[r] = 1 + (self.losses[r] - 1) * self.decay
        if reward:
            self.wins[rail] += 1
        else:
            self.losses[rail] += 1


def simulate(router, seed=7):
    """Yields (rail, reward) per transaction. Each router gets its own seeded RNG."""
    rng = random.Random(seed)
    for t in range(TOTAL):
        rail = router.choose(rng)
        reward = send(rail, t, rng)
        router.learn(rail, reward)
        yield rail, reward


def run_live(routers, speed, window=500):
    """Runs all routers side by side and redraws the chart every `speed` transactions."""
    import matplotlib.pyplot as plt
    plt.ion()
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    fig.subplots_adjust(right=0.82)
    for ax in (top, bottom):
        ax.axvline(DRIFT_AT, linestyle="--", color="grey")
        ax.set_xlim(0, TOTAL)
    top.set_ylim(0.5, 1.0)
    top.set_ylabel(f"Success rate (last {window})")
    bottom.set_ylim(0, 1.0)
    bottom.set_ylabel("Learning router's traffic")
    bottom.set_xlabel("Transaction #")
    bottom.text(DRIFT_AT, 1.02, " Rail A degrades", color="grey", transform=bottom.get_xaxis_transform())
    lines = {r.name: top.plot([], [], label=r.name, lw=2)[0] for r in routers}
    share_lines = {rail: bottom.plot([], [], label=rail, lw=2)[0] for rail in RAILS}
    for ax in (top, bottom):
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    title = fig.suptitle("")

    results = {r.name: ([], []) for r in routers}
    recent = {r.name: deque(maxlen=window) for r in routers}
    recent_picks = deque(maxlen=window)          # the learning router's choices
    xs, rolling, shares = [], {r.name: [] for r in routers}, {rail: [] for rail in RAILS}
    for t, steps in enumerate(zip(*(simulate(r) for r in routers))):
        for r, (rail, reward) in zip(routers, steps):
            results[r.name][0].append(reward)
            results[r.name][1].append(rail)
            recent[r.name].append(reward)
        recent_picks.append(steps[-1][0])
        if t % speed and t != TOTAL - 1:
            continue
        xs.append(t)
        for name, line in lines.items():
            rolling[name].append(sum(recent[name]) / len(recent[name]))
            line.set_data(xs, rolling[name])
        for rail, line in share_lines.items():
            shares[rail].append(recent_picks.count(rail) / len(recent_picks))
            line.set_data(xs, shares[rail])
        saved = sum(results[routers[-1].name][0][DRIFT_AT:]) - sum(results[routers[0].name][0][DRIFT_AT:])
        title.set_text(f"Transaction {t + 1:,} of {TOTAL:,}" +
                       (f"  ·  learning router is {saved:+} payments ahead since the outage" if t >= DRIFT_AT else ""))
        plt.pause(0.001)
    plt.ioff()
    return results


def report(name, history, picks):
    before, after = history[:DRIFT_AT], history[DRIFT_AT:]
    late_picks = picks[-1000:]
    share = {r: late_picks.count(r) / len(late_picks) for r in RAILS}
    print(f"\n{name}")
    print(f"  success rate before outage: {sum(before)/len(before):.1%}")
    print(f"  success rate after outage:  {sum(after)/len(after):.1%}")
    print("  traffic share, last 1000 txns: " +
          ", ".join(f"{r} {s:.0%}" for r, s in share.items()))
    return sum(after)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plot", action="store_true", help="watch it learn on a live chart (needs matplotlib)")
    ap.add_argument("--speed", type=int, default=25, help="transactions per chart frame; lower is slower")
    args = ap.parse_args()

    print(f"Simulating {TOTAL} transactions. Rail A degrades at #{DRIFT_AT}.")
    routers = (FixedRouter(), ThompsonRouter())
    if args.plot:
        results = run_live(routers, max(1, args.speed))
    else:
        results = {}
        for r in routers:
            picks, history = zip(*simulate(r))
            results[r.name] = (list(history), list(picks))
    for name, (h, p) in results.items():
        report(name, h, p)

    saved = sum(results["Learning router"][0][DRIFT_AT:]) - sum(results["Fixed rule"][0][DRIFT_AT:])
    print(f"\nAfter the outage, the learning router completed {saved} more payments "
          f"out of {TOTAL - DRIFT_AT}. Nobody told it anything changed.")

    if args.plot:
        import matplotlib.pyplot as plt
        plt.show()                               # keep the final chart up until closed
