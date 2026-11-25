// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// Devnet experiment: accept a quote only if the dealer's Lighter Core master
/// account holds a hedge of at least `need` in the required direction,
/// read synchronously via READ_CORE in the same transaction.
contract HedgeGate {
    address constant READ_CORE = 0x6600000000000000000000000000000000000000;

    address public immutable dealer;
    bool public immutable dealerIsL1;
    uint16 public immutable marketId;

    event Quoted(address indexed taker, uint64 need, bool needLong, int64 dealerPosition, uint256 evmBlock);

    error NotHedged(int64 position, uint64 need, bool needLong);
    error DealerNotFound();
    error ReadFailed();

    constructor(address dealer_, bool dealerIsL1_, uint16 marketId_) {
        dealer = dealer_;
        dealerIsL1 = dealerIsL1_;
        marketId = marketId_;
    }

    function dealerPosition() public view returns (int64 position) {
        (bool ok, bytes memory res) =
            READ_CORE.staticcall(abi.encodePacked(uint16(0x0007), dealer, dealerIsL1, marketId));
        if (!ok) revert ReadFailed();
        (bool found, bytes memory data) = abi.decode(res, (bool, bytes));
        if (!found) revert DealerNotFound();
        (position,,,,,,,) = abi.decode(data, (int64, uint56, uint16, uint64, uint64, uint8, int128, int64));
    }

    function check(uint64 need, bool needLong) public view returns (bool hedged, int64 position) {
        position = dealerPosition();
        hedged = needLong ? position >= int64(need) : position <= -int64(need);
    }

    /// State-changing path: reverts unless hedged, and records the value read.
    function quote(uint64 need, bool needLong) external {
        (bool hedged, int64 position) = check(need, needLong);
        if (!hedged) revert NotHedged(position, need, needLong);
        emit Quoted(msg.sender, need, needLong, position, block.number);
    }
}
