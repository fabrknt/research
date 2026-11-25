// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IEvmToCoreEntrypoint {
    function createOrder(
        uint48 accountIndex, uint16 marketIndex, uint48 clientOrderIndex, uint8 orderType, uint8 timeInForce,
        uint64 orderExpiry, uint48 amount, uint32 price, bool isAsk, bool reduceOnly, uint32 triggerPrice
    ) external returns (uint64 reqId);
}

/// Devnet experiment: a contract that controls its own Lighter Core account and has no path
/// to EvmToCoreEntrypoint.changePubKey, so the account can never get an API key.
/// It can only open hedges (never reduce-only, never cancel) — step 1 checks the account shape only.
contract KeylessDealer {
    IEvmToCoreEntrypoint constant ENTRY = IEvmToCoreEntrypoint(0x6600000000000000000000000000000000000009);
    address public immutable owner;

    constructor() { owner = msg.sender; }

    function openHedge(uint48 accountIndex, uint16 market, uint48 amount, uint32 price, bool isAsk, uint64 expiry, uint8 tif)
        external returns (uint64 reqId)
    {
        require(msg.sender == owner, "owner");
        reqId = ENTRY.createOrder(accountIndex, market, 0, 0, tif, expiry, amount, price, isAsk, false, 0);
    }
}
