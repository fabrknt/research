package lighter

import (
	"bufio"
	"compress/gzip"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"

	p2 "github.com/elliottech/poseidon_crypto/hash/poseidon2_goldilocks"
)

type (
	Account = account
	Market  = market
	Slot    = slot
)

// Layouts: 2026-05 is the snapshot's; 2026-09 adds the binary options trees (2026-09-20).
const (
	Layout2026May = "2026-05"
	Layout2026Sep = "2026-09"
)

// SetLayout picks the root layout for every hash below. For 2026-09 it first checks the binary options
// tree shape against the prover's EMPTY_MARKET_DATA_TREE_ROOT.
func SetLayout(layout string) error {
	switch layout {
	case Layout2026May:
		binaryLayout = false
	case Layout2026Sep:
		binaryLayout = true
		if emptyMarketDataRoot.ToUint64Array() != [4]uint64{5094422418556072775, 472024594924382182,
			11064781981674099049, 14079628902931319245} {
			return fmt.Errorf("empty market data tree root %v, not the prover's", emptyMarketDataRoot.ToUint64Array())
		}
	default:
		return fmt.Errorf("unknown layout %q", layout)
	}
	return nil
}

// Header is the first line of a state file: export_snapshot.py writes markets only, replay_state.py
// also the batch, its L1 block and the market slots.
type Header struct {
	Batch   uint64          `json:"batch"`
	L1Block uint64          `json:"l1_block"`
	Markets []Market        `json:"markets"`
	Slots   map[string]Slot `json:"slots"`
}

// ReadState reads a state file (.gz for replay_state.py's) and calls each for every account with its
// line as written.
func ReadState(path string, each func(a *Account, line []byte)) (Header, error) {
	var h Header
	f, err := os.Open(path)
	if err != nil {
		return h, err
	}
	defer f.Close()
	var r io.Reader = f
	if strings.HasSuffix(path, ".gz") {
		if r, err = gzip.NewReader(f); err != nil {
			return h, err
		}
	}
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 1<<20), 1<<26)
	if !sc.Scan() {
		return h, fmt.Errorf("%s: empty", path)
	}
	if err := json.Unmarshal(sc.Bytes(), &h); err != nil {
		return h, err
	}
	for sc.Scan() {
		a, err := ParseAccount(sc.Bytes())
		if err != nil {
			return h, err
		}
		each(a, sc.Bytes())
	}
	return h, sc.Err()
}

func ParseAccount(line []byte) (*Account, error) {
	var a Account
	dec := json.NewDecoder(strings.NewReader(string(line)))
	dec.UseNumber()
	if err := dec.Decode(&a); err != nil {
		return nil, err
	}
	return &a, nil
}

func Leaf(a *Account) p2.HashOut                          { return leaf(a) }
func AccountRoot(leaves map[uint64]p2.HashOut) p2.HashOut { return accountRoot(leaves) }
func MarketDataRoot(slots map[string]Slot) p2.HashOut     { return marketDataRoot(slots) }

// MarketsHash in the flat form, or in 16 buckets of 16 (since 38bea38).
func MarketsHash(ms []Market, buckets bool) p2.HashOut {
	if buckets {
		return marketsHashBucketed(ms)
	}
	return marketsHash(ms)
}

// StateRoot as verify_state_root builds it: the market data tree root goes in only in the 2026-09 layout.
func StateRoot(accountRoot, marketsHash p2.HashOut, slots map[string]Slot, validium p2.HashOut) p2.HashOut {
	inputs := []p2.HashOut{accountRoot, marketsHash}
	if binaryLayout {
		inputs = append(inputs, marketDataRoot(slots))
	}
	return p2.HashNToOne(append(inputs, validium))
}

type Encoding struct {
	Name   string
	Decode func([]byte) p2.HashOut
	Encode func(p2.HashOut) []byte
}

// Encodings: the ways four field elements could pack into a bytes32. The first is the one Lighter uses
// (each element 8 bytes little-endian, in order); the others are kept to show they do not match.
func Encodings() []Encoding {
	var out []Encoding
	for _, e := range encodings() {
		out = append(out, Encoding{e.name, e.decode, e.encode})
	}
	return out
}

func FromBytes32(b []byte) p2.HashOut { return encodings()[0].decode(b) }
func ToBytes32(h p2.HashOut) []byte   { return encodings()[0].encode(h) }
func MustHex(s string) []byte         { return mustHex(s) }

// AccountPath: the 48 siblings from an account's leaf up to the account root, leaf level first, and
// that root. leaves must hold every account of the state.
func AccountPath(leaves map[uint64]p2.HashOut, index uint64) ([]p2.HashOut, p2.HashOut) {
	empty := p2.EmptyHashOut()
	level := leaves
	path := make([]p2.HashOut, 0, accountLevels)
	k := index
	for l := 0; l < accountLevels; l++ {
		sib, ok := level[k^1]
		if !ok {
			sib = empty
		}
		path = append(path, sib)
		next := make(map[uint64]p2.HashOut, len(level)/2+1)
		for i := range level {
			parent := i >> 1
			if _, done := next[parent]; done {
				continue
			}
			left, ok := level[parent<<1]
			if !ok {
				left = empty
			}
			right, ok := level[parent<<1|1]
			if !ok {
				right = empty
			}
			next[parent] = p2.HashTwoToOne(left, right)
		}
		level = next
		empty = p2.HashTwoToOne(empty, empty)
		k >>= 1
	}
	return path, level[0]
}

// FoldPath: the account root from a leaf and its path, bit l of the index saying whether the node is
// the right child at level l.
func FoldPath(leafHash p2.HashOut, index uint64, path []p2.HashOut) p2.HashOut {
	node := leafHash
	for _, sib := range path {
		if index&1 == 1 {
			node = p2.HashTwoToOne(sib, node)
		} else {
			node = p2.HashTwoToOne(node, sib)
		}
		index >>= 1
	}
	return node
}

func Hex(h p2.HashOut) string { return "0x" + hex.EncodeToString(ToBytes32(h)) }
