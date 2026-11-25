# Does a model checker find bugs in contracts that were already reviewed? (2026-11-25, 2 contracts)

A claim going around: have an AI read a codebase, write every implicit state transition as an
explicit model, check it in TLA+, and you will find a thousand bugs anywhere. We tried it on two of
our own contracts that had already been through Codex reviews and Foundry tests, and counted what
was real.

**Answer: not a thousand. On a small contract, 0 bugs and 1 rule the spec never stated. On a larger
one with money moving between traders, a pool and a queue, 2 real bugs (plus a third that the
review of the fix found), all three after 10+ review rounds. What found them was writing down the
promise the README makes and checking it, not the model's size.**

## The two contracts

| | [fivemin](https://github.com/fabrknt/fivemin) `FiveMin.sol` | [dayone](https://github.com/fabrknt/dayone) `LaunchPool.sol` |
|---|---|---|
| What | five-minute up/down pools | loss-funded counterparty pool for one HIP-3 perp |
| Lines | 260 | 882 |
| Reviewed before | Codex r1 (CHANGES, fixed) | Codex rounds 1–13 and more, internal arithmetic review |
| Tests before | 23 Foundry | ~60 Foundry + 5 fuzzed invariants |
| Model | `formal/FiveMin.tla` | `formal/LaunchPool.tla` |

## What came out

| | fivemin | dayone |
|---|---|---|
| Safety properties that held | 7 of 7 (20.7M + 39.0M states, two price sources) | 9 of 9 after the fixes (7.4M states, at 2.5% and at 19.99% maintenance) |
| Real bugs | 0 | 2 found by the model, 1 more by the review of the fix |
| Rules the spec never stated | 1 | 1 (the same as bug 2) |
| Known weaknesses re-found | 1 (the poker picks the block, already in the spec) | 0 |
| Mistakes in my own properties | 0 | 3 |
| Seeded bugs caught | 3 of 5 (1 after adding a property, 1 equivalent mutant) | not run |

fivemin, the rule: a round's close and the next round's open are the same moment, but each was
recorded by its own `poke`, so they could take different prices (close 101, next open 99). Not a
loss of money; now one poke records both. [fabrknt/fivemin 6febd65](https://github.com/fabrknt/fivemin/commit/6febd65)

dayone:
1. `_validate` accepted maintenance × max leverage ≥ 100% (10% at 20x). A position at that
   leverage was liquidatable by anyone the moment it opened (its owner lost the open fee), and a
   winning one could not be liquidated at all (an underflow). Needs the operator to set such a
   pair; deployments use 2.5% × 20x. Now refused.
2. The backing check covered "a 10% move up or a 10% move down", the larger of the two. Inside the
   band the price can rise, longs close as winners, and come back, shorts close as winners. With a
   $1,100 seed and $10K a side, $581.50 waited in the queue. The README said winners wait only on
   moves past the band. Now the check adds the two; the same seed backs about half as much when
   both sides are open.
3. Codex, reviewing fix 2: holders could redeem the backing right after both opens settled, and the
   same round trip queued $691.50. The model had excluded redemptions from the property. My first
   fix kept the band around the price at redemption; Codex's next round let the price drift inside
   the open's band, redeemed, and queued $245.75, which my property also hid (I had narrowed the band
   to fit the fix). Now the contract remembers the latest open's price and redemption keeps its band.
   Three review rounds: CHANGES, CHANGES, APPROVE.

[fabrknt/dayone d2dff91](https://github.com/fabrknt/dayone/commit/d2dff91)

## What we learned

- **Where it pays.** Little state and one actor: the model confirms what the tests said. Several
  parties sharing one balance over time (traders, holders, a queue): the model asks questions the
  tests never asked, because a fuzzer drops the calls the contract refuses and an invariant checks
  one state, not a path.
- **The hard part is the property, not the model.** The bugs came from writing the README's own
  sentences as properties ("winners wait only on moves past the band", "a position is not
  liquidatable at its entry"). Three of my properties were wrong: twice they forgot positions
  already closed (TLC's trace showed it in one read), once I narrowed one to fit my own fix (a
  reviewer showed it).
- **Small models hide arithmetic.** At prices 90/100/110 the fee's rounding and the win haircut left
  enough slack that the round trip never queued. The model gave the shape (up, close, down, close);
  a Foundry test at real sizes gave the $581.50. Use both.
- **Check the model has teeth.** On fivemin, a seeded bug (a missed checkpoint voids late) passed
  the first model; it needed one more property. A green run is not evidence until a mutant fails it.
- **A property you exclude is a hole you chose.** The third dayone bug sat exactly in the case the
  property skipped (redemptions), and after the first fix, in the case I had narrowed. Write down
  every exclusion; never change a property in the same step as the fix it checks; ask a reviewer
  to attack the exclusions first.

## The recipe we used

1. List the states the code keeps implicitly (fivemin has no status field: five values decide it).
2. Model the actions with the contract's own arithmetic; leave out what only makes an action wait.
3. Properties: the README's promises, word for word, plus "every exit works" (`CanExit`,
   `LiquidationWorks`); skip what the Foundry invariants already check.
4. Run TLC; turn every counterexample into a Foundry test on the real contract before believing it.
5. Seed a few bugs into the model; a property that catches none is not checking anything.
6. Fix, then have someone else attack the fix and the properties you excluded.

Time: about 2 h for fivemin and 3 h for dayone, most of it TLC running (6–12 min a run) and fixing
my properties.

Measured with an AI (Claude), which wrote the models, the properties, the tests and the fixes; Codex
reviewed the fixes. TLC 1.8.0, Foundry. Not an audit.
