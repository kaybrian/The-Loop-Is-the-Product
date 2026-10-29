# Demo 1: A payment router that learns on its own

**File:** [`demo1_bandit_router.py`](demo1_bandit_router.py) · Part of [The Loop Is the Product](../README.md)

A hard-coded payment router goes up against one that learns. Halfway through, the best rail degrades and nobody tells either router. The learning router notices and moves its traffic. The fixed one never does.

## The loop

| Step | In this demo |
| --- | --- |
| **Act** | Pick a payment rail for the next transaction |
| **Feedback** | The transaction succeeds (1) or fails (0) |
| **Learn** | Update the belief about that rail's success rate |
| **Update** | Future routing follows the new beliefs |

## The setup

Three simulated rails, each with a hidden success rate the routers never see:

| Rail | Transactions 0–2999 | Transactions 3000–5999 |
| --- | --- | --- |
| Rail A | 92% | **60%** (outage) |
| Rail B | 85% | 85% |
| Rail C | 78% | **88%** |

Two routers handle all 6,000 transactions:

- **Fixed rule:** always sends everything through Rail A, the best rail at launch. This is what most of us ship.
- **Learning router:** uses [Thompson sampling](https://en.wikipedia.org/wiki/Thompson_sampling). It keeps a Beta distribution for each rail, samples a plausible success rate from each one, routes to the highest sample, then updates that rail with the result. A `decay` factor slowly forgets old evidence so it can notice when things change.

## Before you start

- **Python 3.9 or newer.** The simulation itself uses only the standard library.
- **`matplotlib`**, only for the live chart.

If you followed the [quick start](../README.md#quick-start), you already have both. Otherwise:

```bash
pip install matplotlib
```

## Run it

Run these from the repo's top folder.

1. **Watch it learn on a live chart:**
   ```bash
   python Demo_1/demo1_bandit_router.py --plot
   ```
   A chart opens and draws itself as transactions happen:
   - **Top panel:** each router's success rate over the last 500 transactions.
   - **Bottom panel:** where the learning router sends its traffic. Watch it leave Rail A after the outage at transaction 3,000.
   - **Title:** a running count of how many more payments the learning router has completed since the outage.

   When the run ends, the summary prints in the terminal and the chart stays open until you close it.

2. **Slow it down while you talk.** `--speed` sets how many transactions go through per chart frame. The default is 25. Lower is slower:
   ```bash
   python Demo_1/demo1_bandit_router.py --plot --speed 10
   ```

3. **Just the numbers, no chart:**
   ```bash
   python Demo_1/demo1_bandit_router.py
   ```

The random seed is fixed, so you get the same numbers every run.

## What you'll see

```
Simulating 6000 transactions. Rail A degrades at #3000.

Fixed rule
  success rate before outage: 92.2%
  success rate after outage:  60.0%
  traffic share, last 1000 txns: Rail A 100%, Rail B 0%, Rail C 0%

Learning router
  success rate before outage: 89.9%
  success rate after outage:  84.3%
  traffic share, last 1000 txns: Rail A 2%, Rail B 14%, Rail C 84%

After the outage, the learning router completed 730 more payments out of 3000. Nobody told it anything changed.
```

Two things to notice:

1. **After the outage**, the fixed rule drops to 60% and stays there. The learning router notices within a few hundred transactions and moves most of its traffic to Rail C.
2. **Before the outage**, the fixed rule does slightly better (92.2% vs 89.9%). The learning router spends some traffic trying other rails. Learning has a cost, and it's worth being honest about that.

## Things to try

- **Change `decay`** in `ThompsonRouter` (default `0.995`). At `1.0` (never forget), old evidence about Rail A keeps it in use long after the outage, and the after-outage success rate falls to about 79%. At `0.9` it forgets so fast that it keeps chasing noise and spreads traffic across all three rails.
- **Write your own outage** by editing `SUCCESS_RATES`, `DRIFTED` and `DRIFT_AT` at the top of the file.
- **Change the seed** in `simulate(router, seed=7)` to check the result isn't a lucky draw.
- **Change the reward.** Add fees or latency to it. What happens if you reward **only** speed?
