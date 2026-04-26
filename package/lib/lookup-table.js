"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.compileLegacyTransactionToV0 = compileLegacyTransactionToV0;
const web3_js_1 = require("@solana/web3.js");
function compileLegacyTransactionToV0({ transaction, lookupTables, }) {
    if (transaction.feePayer == null) {
        throw new Error("transaction.feePayer is required");
    }
    if (transaction.recentBlockhash == null) {
        throw new Error("transaction.recentBlockhash is required");
    }
    const legacySize = transaction.serialize({
        requireAllSignatures: false,
        verifySignatures: false,
    }).length;
    const message = new web3_js_1.TransactionMessage({
        payerKey: transaction.feePayer,
        recentBlockhash: transaction.recentBlockhash,
        instructions: transaction.instructions,
    }).compileToV0Message(lookupTables);
    const versionedTransaction = new web3_js_1.VersionedTransaction(message);
    const v0Size = versionedTransaction.serialize().length;
    return {
        transaction: versionedTransaction,
        legacySize,
        v0Size,
        bytesSaved: legacySize - v0Size,
        usedLookupTables: message.addressTableLookups.map((lookup) => lookup.accountKey.toBase58()),
    };
}
//# sourceMappingURL=lookup-table.js.map