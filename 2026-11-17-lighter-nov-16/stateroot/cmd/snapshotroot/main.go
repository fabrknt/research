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
	"bufio"
	"compress/gzip"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math/big"
	"os"
	"strings"

	g "github.com/elliottech/poseidon_crypto/field/goldilocks"
	p2 "github.com/elliottech/poseidon_crypto/hash/poseidon2_goldilocks"
)

const (
	accountLevels  = 48
	markets        = 255 // POSITION_LIST_SIZE
	bucketSize     = 16  // POSITION_HASH_BUCKET_SIZE; 256 slots (255 markets + one empty) in 16 buckets
	assetLevels    = 6   // 64 asset slots
	sharesListSize = 16
	u16LimbsFor64  = 4  // BIGU16_U64_LIMBS
	u32LimbsFor96  = 3  // BIG_U96_LIMBS
	u32LimbsFor160 = 5  // BIG_U160_LIMBS
	marketLevels   = 12 // MARKET_MERKLE_LEVELS, binary options trees
	binaryOptions  = 2  // MARKET_TYPE_BINARY_OPTIONS
)

// The state's last delta of each market slot (replay_state.py), the market data tree's leaves.
type slot struct {
	Index  uint64 `json:"market_index"`
	Status uint64 `json:"status"`
	Price  uint64 `json:"price"`
	Cap    uint64 `json:"settlement_cap"`
	QEM    uint64 `json:"quote_extension_multiplier"`
}

var binaryLayout bool

type market struct {
	Mark    uint64 `json:"mark"`
	Funding int64  `json:"funding"`
	Quote   uint64 `json:"quote"`
}

type account struct {
	Index     uint64           `json:"i"`
	L1        *string          `json:"l1"`
	Type      uint64           `json:"t"`
	Positions [][3]int64       `json:"p"` // market, position, funding prefix sum
	Assets    [][2]json.Number `json:"a"` // asset index, balance (up to 96 bits)
	Shares    [][2]int64       `json:"s"` // pool index, share amount; sorted by pool index
	Binary    [][2]int64       `json:"b"` // market slot, size (negative = NO)
	PoolInfo  *struct {
		Total    int64 `json:"total_shares"`
		Operator int64 `json:"operator_shares"`
	} `json:"pi"`
}

// sign as a field element: -1, 0 or 1.
func sign(neg, zero bool) g.Element {
	switch {
	case zero:
		return g.Zero()
	case neg:
		return g.Neg(g.One())
	default:
		return g.One()
	}
}

// limbs of |v| in little-endian order, `bits` wide each, padded to n.
func limbs(v *big.Int, bits uint, n int) []g.Element {
	abs := new(big.Int).Abs(v)
	mask := new(big.Int).Sub(new(big.Int).Lsh(big.NewInt(1), bits), big.NewInt(1))
	out := make([]g.Element, n)
	for i := 0; i < n; i++ {
		out[i] = g.FromUint64(new(big.Int).And(abs, mask).Uint64())
		abs.Rsh(abs, bits)
	}
	if abs.Sign() != 0 {
		panic(fmt.Sprintf("%v does not fit in %d limbs of %d bits", v, n, bits))
	}
	return out
}

// BigIntU16 (4 limbs) then its sign, as append_position_pub_data_hash_params does.
func i64u16(v int64) []g.Element {
	b := big.NewInt(v)
	return append(limbs(b, 16, u16LimbsFor64), sign(v < 0, v == 0))
}

// Most accounts touch a few markets, so most buckets hash 16 empty slots: compute that once.
var emptyBucket = func() p2.HashOut {
	var params []g.Element
	for i := 0; i < bucketSize; i++ {
		params = append(params, i64u16(0)...)
		params = append(params, i64u16(0)...)
	}
	return p2.HashNToHashNoPad(params)
}()

func isEmptyBucket(b [][2]int64) bool {
	for _, p := range b {
		if p != [2]int64{} {
			return false
		}
	}
	return true
}

func assetRoot(assets [][2]json.Number) p2.HashOut {
	level := make([]p2.HashOut, 1<<assetLevels)
	for _, a := range assets {
		idx, _ := a[0].Int64()
		bal, ok := new(big.Int).SetString(a[1].String(), 10)
		if !ok {
			panic("bad balance " + a[1].String())
		}
		if bal.Sign() == 0 {
			continue
		}
		elems := append([]g.Element{sign(bal.Sign() < 0, false)}, limbs(bal, 32, u32LimbsFor96)...)
		level[idx] = p2.HashNToHashNoPad(elems)
	}
	empty := p2.EmptyHashOut()
	isEmpty := make([]bool, len(level))
	for i := range level {
		isEmpty[i] = level[i] == p2.EmptyHashOut()
	}
	for n := len(level) / 2; n >= 1; n /= 2 {
		next := p2.HashTwoToOne(empty, empty)
		for j := 0; j < n; j++ {
			// Two empty subtrees hash to the next level's empty hash: skip the permutation.
			if isEmpty[2*j] && isEmpty[2*j+1] {
				level[j], isEmpty[j] = next, true
				continue
			}
			level[j], isEmpty[j] = p2.HashTwoToOne(level[2*j], level[2*j+1]), false
		}
		empty = next
	}
	return level[0]
}

func leaf(a *account) p2.HashOut {
	pos := make([][2]int64, markets+1) // position, funding; the extra slot stays empty
	for _, p := range a.Positions {
		pos[p[0]] = [2]int64{p[1], p[2]}
	}
	var partial []g.Element
	for b := 0; b < len(pos); b += bucketSize {
		if isEmptyBucket(pos[b : b+bucketSize]) {
			partial = append(partial, emptyBucket[:]...)
			continue
		}
		var params []g.Element
		for _, p := range pos[b : b+bucketSize] {
			params = append(params, i64u16(p[1])...) // last funding rate prefix sum first
			params = append(params, i64u16(p[0])...) // then the position
		}
		h := p2.HashNToHashNoPad(params)
		partial = append(partial, h[:]...)
	}
	for i := 0; i < sharesListSize; i++ {
		if i < len(a.Shares) {
			partial = append(partial, g.FromUint64(uint64(a.Shares[i][0])), g.FromInt64(a.Shares[i][1]))
		} else {
			partial = append(partial, g.Zero(), g.Zero())
		}
	}
	var total, operator int64
	if a.PoolInfo != nil {
		total, operator = a.PoolInfo.Total, a.PoolInfo.Operator
	}
	partial = append(partial, g.FromInt64(total), g.FromInt64(operator))
	ph := p2.HashNToHashNoPad(partial)

	elems := append([]g.Element{}, ph[:]...)
	addr := new(big.Int)
	if a.L1 != nil {
		addr.SetString(strings.TrimPrefix(*a.L1, "0x"), 16)
	}
	elems = append(elems, limbs(addr, 32, u32LimbsFor160)...)
	elems = append(elems, g.FromUint64(a.Type))
	if binaryLayout {
		mr := binaryPositionsRoot(a.Binary)
		elems = append(elems, mr[:]...)
	}
	ar := assetRoot(a.Assets)
	elems = append(elems, ar[:]...)
	return p2.HashNToHashNoPad(elems)
}

func marketsHash(ms []market) p2.HashOut {
	var elems []g.Element
	for _, m := range ms {
		f := big.NewInt(m.Funding)
		elems = append(elems, limbs(f, 16, u16LimbsFor64)...)
		elems = append(elems, sign(m.Funding < 0, m.Funding == 0), g.FromUint64(m.Mark), g.FromUint64(m.Quote))
	}
	return p2.HashNToHashNoPad(elems)
}

// Since 38bea38: 255 markets and one empty, hashed in 16 buckets of 16, then the 16 bucket hashes.
func marketsHashBucketed(ms []market) p2.HashOut {
	ext := append(append([]market{}, ms...), market{})
	var out []g.Element
	for b := 0; b < len(ext); b += bucketSize {
		h := marketsHash(ext[b : b+bucketSize])
		out = append(out, h[:]...)
	}
	return p2.HashNToHashNoPad(out)
}

// A sparse tree of marketLevels levels, bit i of the key picking the side at level i, empty
// subtrees hashing up from the zero hash.
func sparseRoot(leaves map[uint64]p2.HashOut, levels int) p2.HashOut {
	empty := p2.EmptyHashOut()
	level := leaves
	for l := 0; l < levels; l++ {
		next := make(map[uint64]p2.HashOut, len(level)/2+1)
		for k := range level {
			parent := k >> 1
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
	}
	if r, ok := level[0]; ok {
		return r
	}
	return empty
}

var emptyMarketDataRoot = sparseRoot(nil, marketLevels)

// An account's binary options positions: leaf H(market type, |size| as four 16-bit limbs, sign).
func binaryPositionsRoot(ps [][2]int64) p2.HashOut {
	if len(ps) == 0 {
		return emptyMarketDataRoot
	}
	leaves := map[uint64]p2.HashOut{}
	for _, p := range ps {
		if p[1] == 0 {
			continue
		}
		leaves[uint64(p[0])] = p2.HashNToHashNoPad(append([]g.Element{g.FromUint64(binaryOptions)}, i64u16(p[1])...))
	}
	return sparseRoot(leaves, marketLevels)
}

// The market data tree: leaf H(market type, status, price, settlement cap, quote extension
// multiplier) for a slot with any of them non-zero, else the zero hash.
func marketDataRoot(slots map[string]slot) p2.HashOut {
	leaves := map[uint64]p2.HashOut{}
	for _, s := range slots {
		if s.Status+s.Price+s.Cap+s.QEM == 0 {
			continue
		}
		leaves[s.Index] = p2.HashNToHashNoPad([]g.Element{g.FromUint64(binaryOptions),
			g.FromUint64(s.Status), g.FromUint64(s.Price), g.FromUint64(s.Cap), g.FromUint64(s.QEM)})
	}
	return sparseRoot(leaves, marketLevels)
}

func accountRoot(leaves map[uint64]p2.HashOut) p2.HashOut {
	empty := p2.EmptyHashOut()
	level := leaves
	for l := 0; l < accountLevels; l++ {
		next := make(map[uint64]p2.HashOut, len(level)/2+1)
		for k := range level {
			parent := k >> 1
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
	}
	return level[0]
}

// The on-chain bytes32 could pack the four elements in a few ways; try each.
type encoding struct {
	name   string
	decode func([]byte) p2.HashOut
	encode func(p2.HashOut) []byte
}

func encodings() []encoding {
	elemLE := func(b []byte) uint64 { return new(big.Int).SetBytes(reverse(b)).Uint64() }
	elemBE := func(b []byte) uint64 { return new(big.Int).SetBytes(b).Uint64() }
	mk := func(name string, rev bool, get func([]byte) uint64, put func(uint64) []byte) encoding {
		return encoding{name,
			func(b []byte) p2.HashOut {
				var h [4]uint64
				for i := 0; i < 4; i++ {
					j := i
					if rev {
						j = 3 - i
					}
					h[j] = get(b[8*i : 8*i+8])
				}
				return p2.HashOutFromUint64Array(h)
			},
			func(h p2.HashOut) []byte {
				u := h.ToUint64Array()
				var out []byte
				for i := 0; i < 4; i++ {
					j := i
					if rev {
						j = 3 - i
					}
					out = append(out, put(u[j])...)
				}
				return out
			}}
	}
	putLE := func(v uint64) []byte { return reverse(new(big.Int).SetUint64(v).FillBytes(make([]byte, 8))) }
	putBE := func(v uint64) []byte { return new(big.Int).SetUint64(v).FillBytes(make([]byte, 8)) }
	return []encoding{
		mk("elements in order, each little-endian", false, elemLE, putLE),
		mk("elements in order, each big-endian", false, elemBE, putBE),
		mk("elements reversed, each little-endian", true, elemLE, putLE),
		mk("elements reversed, each big-endian", true, elemBE, putBE),
	}
}

func reverse(b []byte) []byte {
	out := make([]byte, len(b))
	for i := range b {
		out[len(b)-1-i] = b[i]
	}
	return out
}

func mustHex(s string) []byte {
	b, err := hex.DecodeString(strings.TrimPrefix(s, "0x"))
	if err != nil || len(b) != 32 {
		panic("want a 32-byte hex value: " + s)
	}
	return b
}

func main() {
	layout := flag.String("layout", "2026-05", "root layout: 2026-05 (the snapshot's) or 2026-09 (binary options)")
	flag.Parse()
	binaryLayout = *layout == "2026-09"
	// The prover's EMPTY_MARKET_DATA_TREE_ROOT: checks the binary options tree shape before hashing.
	if binaryLayout && emptyMarketDataRoot.ToUint64Array() != [4]uint64{5094422418556072775, 472024594924382182,
		11064781981674099049, 14079628902931319245} {
		panic(fmt.Sprintf("empty market data tree root %v, not the prover's", emptyMarketDataRoot.ToUint64Array()))
	}
	args := flag.Args()
	f, err := os.Open(args[0])
	if err != nil {
		panic(err)
	}
	stateRoot, validiumRoot := mustHex(args[1]), mustHex(args[2])

	var r io.Reader = f
	if strings.HasSuffix(args[0], ".gz") { // a replay_state.py state file
		if r, err = gzip.NewReader(f); err != nil {
			panic(err)
		}
	}
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 1<<20), 1<<26)
	sc.Scan()
	var header struct {
		Markets []market
		Slots   map[string]slot
	}
	if err := json.Unmarshal(sc.Bytes(), &header); err != nil {
		panic(err)
	}
	leaves := map[uint64]p2.HashOut{}
	for sc.Scan() {
		var a account
		dec := json.NewDecoder(strings.NewReader(sc.Text()))
		dec.UseNumber()
		if err := dec.Decode(&a); err != nil {
			panic(err)
		}
		leaves[a.Index] = leaf(&a)
	}
	if err := sc.Err(); err != nil {
		panic(err)
	}
	acc := accountRoot(leaves)
	fmt.Printf("accounts %d\naccount root %v\n", len(leaves), acc.ToUint64Array())

	type variant struct {
		name string
		hash p2.HashOut
	}
	variants := []variant{
		{"", marketsHash(header.Markets)},
		{"market details in buckets, ", marketsHashBucketed(header.Markets)},
	}
	matched := false
	for _, v := range variants {
		inputs := []p2.HashOut{acc, v.hash}
		if binaryLayout {
			inputs = append(inputs, marketDataRoot(header.Slots))
		}
		for _, e := range encodings() {
			root := p2.HashNToOne(append(append([]p2.HashOut{}, inputs...), e.decode(validiumRoot)))
			got := e.encode(root)
			ok := hex.EncodeToString(got) == hex.EncodeToString(stateRoot)
			matched = matched || ok
			fmt.Printf("%-67s 0x%x match=%v\n", v.name+e.name, got, ok)
		}
	}
	fmt.Printf("%-67s 0x%x\n", "on-chain state root", stateRoot)
	if !matched {
		os.Exit(1)
	}
}
