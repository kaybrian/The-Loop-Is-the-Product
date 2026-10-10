"""
DevFest Demo 1: A payment router that learns on its own.

Three simulated payment rails. Each has a hidden success rate the router
does not know. A fixed-rule router always uses the rail that was best at
launch. A Thompson-sampling router learns from every transaction.

Halfway through, the "best" rail degrades (an outage, a network issue,
a partner change). Watch which router notices.

Run:  python demo1_bandit_router.py
      python demo1_bandit_router.py --plot   (needs matplotlib)
"""
import argparse
import random

RAILS = ["Rail A", "Rail B", "Rail C"]

# Hidden truth. The router never sees these numbers.
SUCCESS_RATES = {"Rail A": 0.92, "Rail B": 0.85, "Rail C": 0.78}
DRIFT_AT = 3000                      # transaction where the world changes
DRIFTED = {"Rail A": 0.60, "Rail B": 0.85, "Rail C": 0.88}
TOTAL = 6000


def true_rate(rail, t):
    return (DRIFTED if t >= DRIFT_AT else SUCCESS_RATES)[rail]


def send(rail, t):
    """Simulate one transaction. Returns 1 for success, 0 for failure."""
    return 1 if random.random() < true_rate(rail, t) else 0


class FixedRouter:
    """What most of us ship: pick the best rail once, hard-code it."""
    name = "Fixed rule"

    def choose(self):
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

    def choose(self):
        samples = {r: random.betavariate(self.wins[r], self.losses[r]) for r in RAILS}
        return max(samples, key=samples.get)

    def learn(self, rail, reward):
        for r in RAILS:                      # forget a little, everywhere
            self.wins[r] = 1 + (self.wins[r] - 1) * self.decay
            self.losses[r] = 1 + (self.losses[r] - 1) * self.decay
        if reward:
            self.wins[rail] += 1
        else:
            self.losses[rail] += 1


def run(router, seed=7, window=500):
    random.seed(seed)
    history, picks = [], []
    for t in range(TOTAL):
        rail = router.choose()
        reward = send(rail, t)
        router.learn(rail, reward)
        history.append(reward)
        picks.append(rail)
    rolling = [sum(history[max(0, i - window):i + 1]) / len(history[max(0, i - window):i + 1])
               for i in range(TOTAL)]
    return history, picks, rolling


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
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    print(f"Simulating {TOTAL} transactions. Rail A degrades at #{DRIFT_AT}.")
    results = {}
    for router in (FixedRouter(), ThompsonRouter()):
        h, p, roll = run(router)
        results[router.name] = (h, p, roll)
        report(router.name, h, p)

    saved = sum(results["Learning router"][0][DRIFT_AT:]) - sum(results["Fixed rule"][0][DRIFT_AT:])
    print(f"\nAfter the outage, the learning router completed {saved} more payments "
          f"out of {TOTAL - DRIFT_AT}. Nobody told it anything changed.")

    if args.plot:
        import matplotlib.pyplot as plt
        for name, (_, _, roll) in results.items():
            plt.plot(roll, label=name)
        plt.axvline(DRIFT_AT, linestyle="--", color="grey", label="Rail A degrades")
        plt.ylabel("Rolling success rate")
        plt.xlabel("Transaction #")
        plt.title("Who notices the world changed?")
        plt.legend()
        plt.tight_layout()
        plt.show()