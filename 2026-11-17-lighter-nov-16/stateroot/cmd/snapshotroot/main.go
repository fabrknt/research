// snapshotroot: hash Lighter's batch-166859 snapshot into a state root and compare it with the root
// committed on Ethereum.
//
//	go run ./cmd/snapshotroot ACCOUNTS.jsonl STATE_ROOT VALIDIUM_ROOT
//
// ACCOUNTS.jsonl comes from export_snapshot.py. STATE_ROOT and VALIDIUM_ROOT are the bytes32 values
// of commitBatch for that batch (newStateRoot, newValidiumRoot). The validium root covers state that
// is not in the blobs (order books and the like), so it is taken as given.
//
// The layout below follows lighter-prover at 2bbc3089 (BUSL-1.1), read and re-written, not copied:
// desertexit/circuits/src/pubdata_account.rs (account leaf), circuit/src/types/market_details.rs
// (all_public_market_details_hash), desertexit/circuits/src/inner_circuit.rs (verify_state_root).
package main

import (
	"bufio"
	"encoding/hex"
	"encoding/json"
	"fmt"
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
	u16LimbsFor64  = 4 // BIGU16_U64_LIMBS
	u32LimbsFor96  = 3 // BIG_U96_LIMBS
	u32LimbsFor160 = 5 // BIG_U160_LIMBS
)

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
	f, err := os.Open(os.Args[1])
	if err != nil {
		panic(err)
	}
	stateRoot, validiumRoot := mustHex(os.Args[2]), mustHex(os.Args[3])

	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 1<<20), 1<<26)
	sc.Scan()
	var header struct{ Markets []market }
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
	mh := marketsHash(header.Markets)
	fmt.Printf("accounts %d\naccount root %v\nmarket details hash %v\n", len(leaves), acc.ToUint64Array(), mh.ToUint64Array())

	matched := false
	for _, e := range encodings() {
		root := p2.HashNToOne([]p2.HashOut{acc, mh, e.decode(validiumRoot)})
		got := e.encode(root)
		ok := hex.EncodeToString(got) == hex.EncodeToString(stateRoot)
		matched = matched || ok
		fmt.Printf("%-40s 0x%x match=%v\n", e.name, got, ok)
	}
	fmt.Printf("on-chain state root                      0x%x\n", stateRoot)
	if !matched {
		os.Exit(1)
	}
}
