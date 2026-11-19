// snapshotroot: hash Lighter's batch-166859 snapshot into a state root and compare it with the root
// committed on Ethereum.
//
//	go run ./cmd/snapshotroot [-layout 2026-09] ACCOUNTS.jsonl STATE_ROOT VALIDIUM_ROOT
//
// ACCOUNTS.jsonl comes from export_snapshot.py, or is a state file of replay_state.py (.gz). STATE_ROOT and VALIDIUM_ROOT are the bytes32 values
// of commitBatch for that batch (newStateRoot, newValidiumRoot). The validium root covers state that
// is not in the blobs (order books and the like), so it is taken as given.
//
// The layout below follows lighter-prover at 2bbc3089 (BUSL-1.1), read and re-written, not copied:
// desertexit/circuits/src/pubdata_account.rs (account leaf), circuit/src/types/market_details.rs
// (all_public_market_details_hash), desertexit/circuits/src/inner_circuit.rs (verify_state_root).
//
// -layout 2026-09 is the layout since binary options (lighter-prover 28ae613d, 2026-09-20; read at
// fa85b33): each account leaf also carries the root of its binary options positions, and the state
// root hashes in a market data tree as well,
// H(H(H(account root, market details hash), market data tree root), validium root). Both trees have
// 12 levels keyed by market slot (desertexit/circuits/src/pubdata_binary_options_position.rs).
//
// In either layout the market details hash is tried both flat and in 16 buckets of 16 (38bea38,
// 2026-09-07), since the batch the bucketed form took effect from has not been checked.
package main

import (
	"encoding/hex"
	"flag"
	"fmt"
	"os"

	p2 "github.com/elliottech/poseidon_crypto/hash/poseidon2_goldilocks"

	"github.com/fabrknt/research/lighter-nov-16/stateroot/lighter"
)

func main() {
	layout := flag.String("layout", lighter.Layout2026May, "root layout: 2026-05 (the snapshot's) or 2026-09 (binary options)")
	flag.Parse()
	if err := lighter.SetLayout(*layout); err != nil {
		panic(err)
	}
	args := flag.Args()
	stateRoot, validiumRoot := lighter.MustHex(args[1]), lighter.MustHex(args[2])

	leaves := map[uint64]p2.HashOut{}
	header, err := lighter.ReadState(args[0], func(a *lighter.Account, _ []byte) { leaves[a.Index] = lighter.Leaf(a) })
	if err != nil {
		panic(err)
	}
	acc := lighter.AccountRoot(leaves)
	fmt.Printf("accounts %d\naccount root %v\n", len(leaves), acc.ToUint64Array())

	matched := false
	for _, buckets := range []bool{false, true} {
		name := ""
		if buckets {
			name = "market details in buckets, "
		}
		mh := lighter.MarketsHash(header.Markets, buckets)
		for _, e := range lighter.Encodings() {
			got := e.Encode(lighter.StateRoot(acc, mh, header.Slots, e.Decode(validiumRoot)))
			ok := hex.EncodeToString(got) == hex.EncodeToString(stateRoot)
			matched = matched || ok
			fmt.Printf("%-67s 0x%x match=%v\n", name+e.Name, got, ok)
		}
	}
	fmt.Printf("%-67s 0x%x\n", "on-chain state root", stateRoot)
	if !matched {
		os.Exit(1)
	}
}
