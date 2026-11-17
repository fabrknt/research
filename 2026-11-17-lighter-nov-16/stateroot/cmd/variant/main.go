// variant: which of poseidon_crypto's two Poseidon2 implementations reproduces Lighter's empty-tree
// hashes (EMPTY_DELTA_TREE_HASHES in lighter-prover circuit/src/types/constants.rs at 2bbc3089).
package main

import (
	"fmt"

	p2 "github.com/elliottech/poseidon_crypto/hash/poseidon2_goldilocks"
	p2p "github.com/elliottech/poseidon_crypto/hash/poseidon2_goldilocks_plonky2"
)

// Levels 1 and 2 of EMPTY_DELTA_TREE_HASHES; level 0 is the zero hash.
var want = [][4]uint64{
	{7182099517097165596, 9311216678150108034, 8831900494918587432, 10774846510254277933},
	{7544744595273422282, 6210592528081981646, 13108907452876819928, 12505825290281357043},
}

func main() {
	a := p2.HashOutFromUint64Array([4]uint64{})
	b := p2p.HashOutFromUint64Array([4]uint64{})
	for i, w := range want {
		a = p2.HashTwoToOne(a, a)
		b = p2p.HashTwoToOne(b, b)
		fmt.Printf("level %d\n  want    %v\n  p2      %v %v\n  plonky2 %v %v\n", i+1, w,
			a.ToUint64Array(), a.ToUint64Array() == w, b.ToUint64Array(), b.ToUint64Array() == w)
	}
}
