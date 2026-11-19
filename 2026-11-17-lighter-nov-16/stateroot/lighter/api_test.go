package lighter

import (
	"testing"

	g "github.com/elliottech/poseidon_crypto/field/goldilocks"
	p2 "github.com/elliottech/poseidon_crypto/hash/poseidon2_goldilocks"
)

// A path from AccountPath folds back to AccountRoot's root, for neighbours, far-apart and edge indices,
// and stops doing so when the leaf or a sibling changes.
func TestAccountPath(t *testing.T) {
	leaves := map[uint64]p2.HashOut{}
	for i, k := range []uint64{0, 1, 2, 7, 1000, 1001, 1 << 40, 1<<48 - 1} {
		leaves[k] = p2.HashNToHashNoPad([]g.Element{g.FromUint64(uint64(i) + 1)})
	}
	root := AccountRoot(leaves)
	for k, leaf := range leaves {
		path, r := AccountPath(leaves, k)
		if r != root {
			t.Fatalf("AccountPath root differs from AccountRoot")
		}
		if FoldPath(leaf, k, path) != root {
			t.Fatalf("index %d: path does not fold to the root", k)
		}
		if FoldPath(leaves[0], k^1, path) == root {
			t.Fatalf("index %d: a neighbour index folds to the root", k)
		}
		path[len(path)/2] = p2.HashTwoToOne(path[len(path)/2], path[len(path)/2])
		if FoldPath(leaf, k, path) == root {
			t.Fatalf("index %d: a changed sibling still folds to the root", k)
		}
	}
}

func TestEmptyMarketDataRoot(t *testing.T) {
	if err := SetLayout(Layout2026Sep); err != nil {
		t.Fatal(err)
	}
}
