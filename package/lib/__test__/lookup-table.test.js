"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const vitest_1 = require("vitest");
const web3_js_1 = require("@solana/web3.js");
const lookup_table_js_1 = require("../lookup-table.js");
const index_js_1 = require("../instructions/ephemeral-spl-token-program/index.js");
const MAX_DEACTIVATION_SLOT = BigInt("18446744073709551615");
function createLookupTable(key, addresses) {
    return new web3_js_1.AddressLookupTableAccount({
        key,
        state: {
            deactivationSlot: MAX_DEACTIVATION_SLOT,
            lastExtendedSlot: 0,
            lastExtendedSlotStartIndex: 0,
            authority: undefined,
            addresses,
        },
    });
}
function collectNonSignerAccounts(transaction) {
    const byAddress = new Map();
    for (const instruction of transaction.instructions) {
        byAddress.set(instruction.programId.toBase58(), instruction.programId);
        for (const key of instruction.keys) {
            if (!key.isSigner) {
                byAddress.set(key.pubkey.toBase58(), key.pubkey);
            }
        }
    }
    return [...byAddress.values()];
}
(0, vitest_1.describe)("compileLegacyTransactionToV0", () => {
    (0, vitest_1.it)("throws when feePayer is missing", () => {
        const transaction = new web3_js_1.Transaction();
        transaction.recentBlockhash = "11111111111111111111111111111111";
        (0, vitest_1.expect)(() => (0, lookup_table_js_1.compileLegacyTransactionToV0)({
            transaction,
            lookupTables: [],
        })).toThrow("transaction.feePayer is required");
    });
    (0, vitest_1.it)("throws when recentBlockhash is missing", () => {
        const transaction = new web3_js_1.Transaction();
        transaction.feePayer = web3_js_1.Keypair.generate().publicKey;
        (0, vitest_1.expect)(() => (0, lookup_table_js_1.compileLegacyTransactionToV0)({
            transaction,
            lookupTables: [],
        })).toThrow("transaction.recentBlockhash is required");
    });
    (0, vitest_1.it)("compiles a prepared legacy transaction to v0 using lookup tables", async () => {
        const from = web3_js_1.Keypair.generate().publicKey;
        const to = web3_js_1.Keypair.generate().publicKey;
        const mint = web3_js_1.Keypair.generate().publicKey;
        const validator = web3_js_1.Keypair.generate().publicKey;
        const instructions = await (0, index_js_1.transferSpl)(from, to, mint, 25n, {
            visibility: "private",
            fromBalance: "base",
            toBalance: "base",
            validator,
            shuttleId: 7,
            privateTransfer: {
                minDelayMs: 100n,
                maxDelayMs: 300n,
                split: 4,
            },
        });
        const transaction = new web3_js_1.Transaction();
        const lookupTableKey = new web3_js_1.PublicKey("AddressLookupTab1e1111111111111111111111111");
        transaction.feePayer = from;
        transaction.recentBlockhash = "11111111111111111111111111111111";
        transaction.add(...instructions);
        const lookupTable = createLookupTable(lookupTableKey, collectNonSignerAccounts(transaction));
        const result = (0, lookup_table_js_1.compileLegacyTransactionToV0)({
            transaction,
            lookupTables: [lookupTable],
        });
        (0, vitest_1.expect)(result.usedLookupTables).toEqual([lookupTableKey.toBase58()]);
        (0, vitest_1.expect)(result.transaction.message.addressTableLookups).toHaveLength(1);
        (0, vitest_1.expect)(result.bytesSaved).toBeGreaterThan(0);
        (0, vitest_1.expect)(result.v0Size).toBeLessThan(result.legacySize);
    });
    (0, vitest_1.it)("returns no used lookup tables when none of the addresses match", async () => {
        const from = web3_js_1.Keypair.generate().publicKey;
        const to = web3_js_1.Keypair.generate().publicKey;
        const mint = web3_js_1.Keypair.generate().publicKey;
        const validator = web3_js_1.Keypair.generate().publicKey;
        const instructions = await (0, index_js_1.transferSpl)(from, to, mint, 25n, {
            visibility: "private",
            fromBalance: "base",
            toBalance: "base",
            validator,
            shuttleId: 7,
            privateTransfer: {
                minDelayMs: 100n,
                maxDelayMs: 300n,
                split: 4,
            },
        });
        const transaction = new web3_js_1.Transaction();
        const unrelatedLookupTable = createLookupTable(new web3_js_1.PublicKey("11111111111111111111111111111111"), [web3_js_1.Keypair.generate().publicKey]);
        transaction.feePayer = from;
        transaction.recentBlockhash = "11111111111111111111111111111111";
        transaction.add(...instructions);
        const result = (0, lookup_table_js_1.compileLegacyTransactionToV0)({
            transaction,
            lookupTables: [unrelatedLookupTable],
        });
        (0, vitest_1.expect)(result.usedLookupTables).toEqual([]);
        (0, vitest_1.expect)(result.transaction.message.addressTableLookups).toHaveLength(0);
    });
});
//# sourceMappingURL=lookup-table.test.js.map