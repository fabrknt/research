#!/usr/bin/env bash
# Reproduce the hedge-gate test on the Lighter EVM devnet.
#
# Needs two throwaway keys in the environment (never commit them):
#   DEALER_KEY  the account whose Core position the gate reads
#   TAKER_KEY   the counterparty, which also deploys the gate
# Fund the dealer first at https://faucet.devnet.lighterevm.axiom.xyz
# (Lighter EVM ETH and Lighter EVM USDC; the faucet asks for a Turnstile check).
# Devnet resets wipe state; read docs.lighter.xyz/evm/changelog before rerunning.
set -euo pipefail

R=https://evm-rpc.devnet.lighterevm.axiom.xyz
CORE_API=https://core-api.devnet.lighterevm.axiom.xyz
USDC=0x10846f5B52bf7962FaBAC54EbBf981A03acdBE1a   # wUSDC on Lighter EVM (devnet 1.3.0)
MANAGER=0x6600000000000000000000000000000000000001  # EvmInteropManager
ENTRY=0x6600000000000000000000000000000000000009    # EvmToCoreEntrypoint
READ_CORE=0x6600000000000000000000000000000000000000
MARKET=0          # ETH-PERP
AMOUNT=100        # 0.01 ETH (size decimals 4)

DEALER=$(cast wallet address --private-key "$DEALER_KEY")
TAKER=$(cast wallet address --private-key "$TAKER_KEY")
pause() { python3 -I -c 'import time,sys; time.sleep(float(sys.argv[1]))' "$1"; }

# Core account index of an EVM-controlled master account (READ_CORE selector 0x0001).
account_index() {
  local raw inner
  raw=$(cast call $READ_CORE "$(cast concat-hex 0x0001 "$1" 0x00)" --rpc-url $R)
  inner=$(cast abi-decode "f()(bool,bytes)" "$raw" | tail -1)
  cast abi-decode 'f()(uint8,uint48,uint48,address,address,int128)' "$inner" | sed -n 2p | awk '{print $1}'
}

echo "1. split the faucet: half the ETH and USDC to the taker"
cast send "$TAKER" --value 0.004ether --private-key "$DEALER_KEY" --rpc-url $R >/dev/null
cast send $USDC "transfer(address,uint256)" "$TAKER" 50000000 --private-key "$DEALER_KEY" --rpc-url $R >/dev/null

echo "2. deposit 45 USDC each into Core (perps route); the first deposit creates the Core account"
for KEY in "$DEALER_KEY" "$TAKER_KEY"; do
  ADDR=$(cast wallet address --private-key "$KEY")
  cast send $USDC "approve(address,uint256)" $MANAGER 45000000 --private-key "$KEY" --rpc-url $R >/dev/null
  cast send $MANAGER "sendToCore(uint32,address,bool,uint256,uint8)" 3 "$ADDR" false 45000000 0 \
    --private-key "$KEY" --rpc-url $R >/dev/null
done
pause 5
DI=$(account_index "$DEALER"); TI=$(account_index "$TAKER")
echo "   dealer account $DI, taker account $TI"

# Price at the current index, from READ_CORE market info (selector 0x0005).
raw=$(cast call $READ_CORE 0x0005$(printf '%04x' $MARKET) --rpc-url $R)
inner=$(cast abi-decode "f()(bool,bytes)" "$raw" | tail -1)
PRICE=$(cast abi-decode 'f()(uint8,uint32,uint32,uint32,uint32,uint64,uint64,uint32,uint64,uint64,uint32,int64,uint64)' "$inner" | sed -n 9p | awk '{print $1}')
EXP=$(( ($(date +%s) + 3600) * 1000 ))
SIG="createOrder(uint48,uint16,uint48,uint8,uint8,uint64,uint48,uint32,bool,bool,uint32)"

echo "3. the dealer rests a bid, the taker sells into it (IOC): dealer long $AMOUNT at $PRICE"
cast send $ENTRY "$SIG" "$DI" $MARKET 1 0 1 $EXP $AMOUNT "$PRICE" false false 0 --private-key "$DEALER_KEY" --rpc-url $R >/dev/null
pause 4
cast send $ENTRY "$SIG" "$TI" $MARKET 1 0 0 0 $AMOUNT "$PRICE" true false 0 --private-key "$TAKER_KEY" --rpc-url $R >/dev/null
pause 4

echo "4. deploy the gate with the dealer's Core account"
G=$(forge create src/HedgeGate.sol:HedgeGate --broadcast --private-key "$TAKER_KEY" --rpc-url $R \
  --constructor-args "$DEALER" false $MARKET 2>/dev/null | awk '/Deployed to:/ {print $3}')
echo "   gate $G"
for need in $AMOUNT $((AMOUNT + 1)); do
  for long in true false; do
    echo "   check($need, long=$long): $(cast call "$G" 'check(uint64,bool)(bool,int64)' $need $long --rpc-url $R | tr '\n' ' ')"
  done
done
cast send "$G" "quote(uint64,bool)" $AMOUNT true --private-key "$TAKER_KEY" --rpc-url $R >/dev/null && echo "   quote($AMOUNT) accepted"
cast call "$G" "quote(uint64,bool)" $((AMOUNT + 50)) true --from "$TAKER" --rpc-url $R 2>&1 | grep -o 'NotHedged([^)]*)' || true

echo "5. the dealer closes (taker rests a bid, dealer sells reduce-only IOC); trace the gate block by block"
cast send $ENTRY "$SIG" "$TI" $MARKET 2 0 1 $EXP $AMOUNT "$PRICE" false false 0 --private-key "$TAKER_KEY" --rpc-url $R >/dev/null
pause 4
CLOSE_BLOCK=$(cast send $ENTRY "$SIG" "$DI" $MARKET 2 0 0 0 $AMOUNT "$PRICE" true true 0 \
  --private-key "$DEALER_KEY" --rpc-url $R --json | python3 -I -c 'import json,sys; print(int(json.load(sys.stdin)["blockNumber"], 16))')
pause 10
echo "   close sent in EVM block $CLOSE_BLOCK"
for b in $(seq $((CLOSE_BLOCK - 2)) $((CLOSE_BLOCK + 8))); do
  parent=$(cast block "$b" --rpc-url $R --json | python3 -I -c 'import json,sys; print(int(json.load(sys.stdin)["extraData"], 16))')
  echo "   evm $b parentCore $parent check=$(cast call "$G" 'check(uint64,bool)(bool,int64)' $AMOUNT true --block "$b" --rpc-url $R | tr '\n' ' ')"
done
curl -s "$CORE_API/api/v1/recentTrades?market_id=$MARKET&limit=1" | python3 -I -c \
  'import json,sys; t=json.load(sys.stdin)["trades"][0]; print("   core trade block", t["block_height"], "size", t["size"])'
