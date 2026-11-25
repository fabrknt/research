# Machine-code proofs of RustCrypto, checked on a laptop (2026-11-25)

[intrinsic-technologies/rustcrypto-fv](https://github.com/intrinsic-technologies/rustcrypto-fv)
(published 2026-11-20) states in Lean that the compiled x86-64 code of ten RustCrypto crates computes
the published standard (FIPS 180-4, SECG, RFCs): 71 theorems. Each says that a well-formed call returns,
writes the standard's output, writes nothing but the output and the stack, and leaves the callee-saved
registers as they were. The statements and the proofs are separate modules; comparator checks that each
proof proves exactly the statement, with only `propext`, `Quot.sound` and `Classical.choice`.

The question: can one person check one crate end to end on their own machine, following the README, and
what does it cost? We ran `sha2` 0.11.1 (12 theorems: six hashers, one-shot and in parts).

## Answer

Yes. All three steps passed, on an Apple M2 Pro (12 cores, 32 GB), macOS 26.6, rustcrypto-fv `8aa4609`,
Lean 4.34.0, lean-x86 and lean-x86-proofs v0.0.2:

| Step | Result | Wall time | CPU (user + sys) |
|---|---|---:|---:|
| `lake build Sha2.Statements` (with lean-x86) | 958 jobs, built | 3 min 40 s | 733 s + 407 s |
| `lake build Sha2.Proofs` | 2,661 jobs, 0 errors | 5 h 17 min | 8,160 s + 3,391 s |
| `scripts/comparator-local.sh Sha2` | "Lean default kernel accepts the solution" | 1 h 33 min | 2,266 s + 1,177 s |

The proofs are 237,356 lines in 1,105 files, against a 364-line `Statements.lean`. Three files of the
SHA-512 compression proof took most of the proof build's time: `Refinement.Part52` 9,811 s,
`Part42` 4,444 s, `Part41` 2,154 s, against 11,066 s for the other 2,658 jobs together (per-job times, run
in parallel, from `proofs.log`).

The wall times are not clean: the Mac slept with the lid closed from 18:02 to 19:51, during the SHA-512
files (`Part41` and `Part42` include it); why `Part52` took 2.7 h with the machine awake was not measured (system time was about 30% of CPU). `run.sh` now keeps the machine
awake. Treat 5 h as an upper bound for this machine, not a benchmark.

## What it does and does not give a user of the crates

- It is about one binary: the crate built `no_std` for `x86_64-unknown-none` at x86-64-v1, linked at a
  fixed address and extracted to `Sha2/Spec/Program/Extracted/`. A program that depends on `sha2` and
  is built another way (another target, SHA-NI, another layout) is not covered by these theorems.
- Our own Rust repositories mostly depend on `sha2` 0.10 and `k256` 0.13, not the verified 0.11.1 and
  0.14.0, so none of them can say it uses the verified code.
- The trust left is lean-x86's machine model of the processor and the conditions the theorems assume
  (identity-mapped first 4 GiB, no pending interrupts, write-back memory).

## Next to it on Solana

The same shape for Solana programs (prove that compiled sBPF writes only the accounts it should) is
where [solana-foundation/leanprover-solanalib](https://github.com/solana-foundation/leanprover-solanalib)
is heading: an sBPF semantics ported from the OOPSLA 2025 Isabelle model, a model of the Agave 4.3.2
runtime, and contracts for 53 crates including `anchor-lang` and `pinocchio`, with models contributed by
Harmonic (2026-11-24) and used by Certora's Lusterna. Its README says plainly that it is not yet a proof
about the compiled program. We are not building that layer ourselves.

## Reproduce

```sh
./run.sh Sha2 ~/src/_ext   # needs elan and a GitHub SSH key; about 7 h on the machine above
```

`statements.log`, `proofs.log` and `comparator.log` are the outputs of the run above (home directory
replaced by `~`).
