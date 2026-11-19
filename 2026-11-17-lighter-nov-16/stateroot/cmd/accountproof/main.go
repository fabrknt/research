// accountproof: prove one Lighter account's state against the state root committed on Ethereum, and
// check such a proof with nothing but the proof and that root.
//
//	go run ./cmd/accountproof prove [-layout 2026-09] STATE ACCOUNT STATE_ROOT VALIDIUM_ROOT > proof.json
//	go run ./cmd/accountproof verify proof.json STATE_ROOT
//
// STATE is a state file (export_snapshot.py's, or replay_state.py's .gz); STATE_ROOT and VALIDIUM_ROOT
// are the bytes32 values committed for its batch (../../2026-11-18-lighter-state-replay/roots.py).
// prove hashes the whole state once (about 10 minutes) and refuses if it does not reach STATE_ROOT.
//
// The proof holds the account's leaf preimage as the state file has it, its 48 siblings, every market's
// public details (mark price, funding prefix sum, quote multiplier) and, since 2026-09, every market
// slot, so that verify recomputes the leaf, the account root, the market details hash and the market
// data tree from the proof itself. The validium root is taken as given: it covers state that is not
// published (order books and the like).
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"

	p2 "github.com/elliottech/poseidon_crypto/hash/poseidon2_goldilocks"

	"github.com/fabrknt/research/lighter-nov-16/stateroot/lighter"
)

type proof struct {
	Batch          uint64                  `json:"batch"`
	Layout         string                  `json:"layout"`
	MarketsBuckets bool                    `json:"market_details_in_buckets"`
	Account        json.RawMessage         `json:"account"`
	Path           [][4]uint64             `json:"path"` // siblings, leaf level first
	Markets        []lighter.Market        `json:"markets"`
	Slots          map[string]lighter.Slot `json:"slots,omitempty"`
	ValidiumRoot   string                  `json:"validium_root"`
	StateRoot      string                  `json:"state_root"` // as committed; verify takes its own
}

func fail(format string, a ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", a...)
	os.Exit(1)
}

func prove(args []string) {
	fs := flag.NewFlagSet("prove", flag.ExitOnError)
	layout := fs.String("layout", lighter.Layout2026May, "root layout: 2026-05 or 2026-09")
	fs.Parse(args)
	if fs.NArg() != 4 {
		fail("usage: prove [-layout L] STATE ACCOUNT STATE_ROOT VALIDIUM_ROOT")
	}
	if err := lighter.SetLayout(*layout); err != nil {
		fail("%v", err)
	}
	var index uint64
	if _, err := fmt.Sscan(fs.Arg(1), &index); err != nil {
		fail("account: %v", err)
	}
	stateRoot, validium := lighter.MustHex(fs.Arg(2)), lighter.FromBytes32(lighter.MustHex(fs.Arg(3)))

	leaves := map[uint64]p2.HashOut{}
	var line []byte
	header, err := lighter.ReadState(fs.Arg(0), func(a *lighter.Account, l []byte) {
		leaves[a.Index] = lighter.Leaf(a)
		if a.Index == index {
			line = append([]byte{}, l...)
		}
	})
	if err != nil {
		fail("%v", err)
	}
	if line == nil {
		fail("account %d is not in %s", index, fs.Arg(0))
	}
	path, acc := lighter.AccountPath(leaves, index)
	buckets, found := false, false
	for _, b := range []bool{false, true} {
		root := lighter.StateRoot(acc, lighter.MarketsHash(header.Markets, b), header.Slots, validium)
		if strings.EqualFold(lighter.Hex(root), "0x"+fmt.Sprintf("%x", stateRoot)) {
			buckets, found = b, true
			break
		}
	}
	if !found {
		fail("the state does not hash to %s in layout %s: no proof", fs.Arg(2), *layout)
	}
	p := proof{Batch: header.Batch, Layout: *layout, MarketsBuckets: buckets, Account: line,
		Markets: header.Markets, ValidiumRoot: fs.Arg(3), StateRoot: fs.Arg(2)}
	if *layout == lighter.Layout2026Sep {
		p.Slots = header.Slots
	}
	for _, s := range path {
		p.Path = append(p.Path, s.ToUint64Array())
	}
	out, _ := json.MarshalIndent(p, "", " ")
	fmt.Println(string(out))
}

func verify(args []string) {
	if len(args) != 2 {
		fail("usage: verify PROOF.json STATE_ROOT")
	}
	raw, err := os.ReadFile(args[0])
	if err != nil {
		fail("%v", err)
	}
	var p proof
	if err := json.Unmarshal(raw, &p); err != nil {
		fail("%v", err)
	}
	if err := lighter.SetLayout(p.Layout); err != nil {
		fail("%v", err)
	}
	a, err := lighter.ParseAccount(p.Account)
	if err != nil {
		fail("account: %v", err)
	}
	if len(p.Path) != 48 {
		fail("path has %d siblings, want 48", len(p.Path))
	}
	path := make([]p2.HashOut, len(p.Path))
	for i, s := range p.Path {
		path[i] = p2.HashOutFromUint64Array(s)
	}
	acc := lighter.FoldPath(lighter.Leaf(a), a.Index, path)
	root := lighter.StateRoot(acc, lighter.MarketsHash(p.Markets, p.MarketsBuckets), p.Slots,
		lighter.FromBytes32(lighter.MustHex(p.ValidiumRoot)))
	want := strings.ToLower(args[1])
	fmt.Printf("batch %d, account %d\ncomputed state root  %s\ngiven state root     %s\n", p.Batch, a.Index, lighter.Hex(root), want)
	if lighter.Hex(root) != want {
		fail("NO MATCH: the proof does not reach this root")
	}
	fmt.Println("match: this account state is in the committed root")
	fmt.Printf("  l1 address  %s\n", deref(a.L1))
	for _, x := range a.Assets {
		fmt.Printf("  asset %s balance %s\n", x[0], x[1])
	}
	for _, x := range a.Positions {
		fmt.Printf("  market %d position %d (funding prefix sum %d)\n", x[0], x[1], x[2])
	}
	for _, x := range a.Binary {
		fmt.Printf("  binary options slot %d size %d\n", x[0], x[1])
	}
	for _, x := range a.Shares {
		fmt.Printf("  pool %d shares %d\n", x[0], x[1])
	}
}

func deref(s *string) string {
	if s == nil {
		return "(none)"
	}
	return *s
}

func main() {
	if len(os.Args) < 2 {
		fail("usage: accountproof prove|verify ...")
	}
	switch os.Args[1] {
	case "prove":
		prove(os.Args[2:])
	case "verify":
		verify(os.Args[2:])
	default:
		fail("unknown command %q", os.Args[1])
	}
}
