// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IEvmToCoreEntrypoint {
    function createOrder(
        uint48 accountIndex, uint16 marketIndex, uint48 clientOrderIndex, uint8 orderType, uint8 timeInForce,
        uint64 orderExpiry, uint48 amount, uint32 price, bool isAsk, bool reduceOnly, uint32 triggerPrice
    ) external returns (uint64 reqId);
}

interface IERC20 {
    function transferFrom(address, address, uint256) external returns (bool);
    function transfer(address, uint256) external returns (bool);
}

/// Devnet experiment: a dealer whose hedge lives in a Lighter Core account that this contract
/// controls and that can never get an API key (no changePubKey path, no proxy, no delegatecall).
///
/// A trade is confirmed in two steps, because writes to Core are asynchronous:
///   1. request(): the taker escrows a fee and the contract sends an IOC hedge order to Core.
///   2. settle(), in a later block: the contract reads the hedge's result with READ_CORE and
///      confirms the trade for the filled amount only, refunding the rest of the fee.
/// There is no reduce path: once confirmed, the hedge can only leave through liquidation or ADL.
contract HedgedRFQ {
    address constant READ_CORE = 0x6600000000000000000000000000000000000000;
    IEvmToCoreEntrypoint constant ENTRY = IEvmToCoreEntrypoint(0x6600000000000000000000000000000000000009);

    IERC20 public immutable usdc;
    uint16 public immutable market;

    enum State { None, Pending, Confirmed, Refunded }

    struct Trade {
        address taker;
        bool takerBuys;
        uint48 size;
        uint256 fee;
        uint64 reqId;
        State state;
        uint48 filled;
    }

    Trade[] public trades;
    /// Net size the dealer owes takers (positive: takers are long against the dealer).
    int64 public takersNet;

    event Requested(uint256 indexed id, address indexed taker, bool takerBuys, uint48 size, uint64 reqId);
    event Settled(uint256 indexed id, State state, uint48 filled, uint8 coreStatus, uint32 coreError, uint8 orderStatus);

    error StillPending();
    error NotPending();
    error ReadFailed();

    constructor(IERC20 usdc_, uint16 market_) {
        usdc = usdc_;
        market = market_;
    }

    function coreAccount() public view returns (uint48 idx) {
        (bool found, bytes memory data) = _read(abi.encodePacked(uint16(0x0009), address(this)));
        require(found, "no core account");
        idx = abi.decode(data, (uint48));
    }

    function hedgePosition() public view returns (int64 position) {
        (bool found, bytes memory data) = _read(abi.encodePacked(uint16(0x0007), address(this), false, market));
        if (!found) return 0;
        (position,,,,,,,) = abi.decode(data, (int64, uint56, uint16, uint64, uint64, uint8, int128, int64));
    }

    /// The dealer is covered when its Core position offsets everything it owes takers.
    function covered() external view returns (bool ok, int64 position, int64 owed) {
        position = hedgePosition();
        owed = takersNet;
        ok = position == owed;
    }

    /// Step 1. Taker buys `size` from the dealer (or sells, if !takerBuys); the dealer hedges by
    /// trading the same direction on Core with an IOC limit at `limitPrice`.
    function request(bool takerBuys, uint48 size, uint32 limitPrice, uint256 fee) external returns (uint256 id) {
        require(usdc.transferFrom(msg.sender, address(this), fee), "fee");
        uint64 reqId = ENTRY.createOrder(coreAccount(), market, 0, 0, 0, 0, size, limitPrice, !takerBuys, false, 0);
        id = trades.length;
        trades.push(Trade(msg.sender, takerBuys, size, fee, reqId, State.Pending, 0));
        emit Requested(id, msg.sender, takerBuys, size, reqId);
    }

    /// Step 2. Anyone may call once Core has a final answer for the hedge.
    function settle(uint256 id) external {
        Trade storage t = trades[id];
        if (t.state != State.Pending) revert NotPending();

        (uint8 coreStatus, bytes memory resp) = _txStatus(t.reqId);
        if (coreStatus == 0) revert StillPending();

        uint48 filled;
        uint32 coreError;
        uint8 orderStatus;
        if (coreStatus == 1) {
            uint64 orderIndex = abi.decode(resp, (uint64));
            (bool found, bytes memory data) = _read(abi.encodePacked(uint16(0x000A), orderIndex));
            if (!found) revert StillPending();
            (orderStatus, filled,,,) = abi.decode(data, (uint8, uint48, uint48, uint32, uint32));
            if (orderStatus < 3) revert StillPending(); // IOC: wait for filled (3) or canceled (4)
        } else {
            coreError = abi.decode(resp, (uint32));
        }

        t.filled = filled;
        uint256 refund = t.fee - (t.fee * filled) / t.size;
        if (filled > 0) {
            t.state = State.Confirmed;
            takersNet += t.takerBuys ? int64(uint64(filled)) : -int64(uint64(filled));
        } else {
            t.state = State.Refunded;
        }
        if (refund > 0) require(usdc.transfer(t.taker, refund), "refund");
        emit Settled(id, t.state, filled, coreStatus, coreError, orderStatus);
    }

    function tradeCount() external view returns (uint256) {
        return trades.length;
    }

    function _txStatus(uint64 reqId) internal view returns (uint8 status, bytes memory data) {
        (bool ok, bytes memory res) = READ_CORE.staticcall(abi.encodePacked(uint16(0x0000), reqId));
        if (!ok) revert ReadFailed();
        (status, data) = abi.decode(res, (uint8, bytes));
    }

    function _read(bytes memory query) internal view returns (bool found, bytes memory data) {
        (bool ok, bytes memory res) = READ_CORE.staticcall(query);
        if (!ok) revert ReadFailed();
        (found, data) = abi.decode(res, (bool, bytes));
    }
}
