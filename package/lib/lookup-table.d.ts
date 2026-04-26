import { AddressLookupTableAccount, Transaction, VersionedTransaction } from "@solana/web3.js";
export interface CompileLegacyTransactionToV0Input {
    transaction: Transaction;
    lookupTables: AddressLookupTableAccount[];
}
export interface CompileLegacyTransactionToV0Result {
    transaction: VersionedTransaction;
    legacySize: number;
    v0Size: number;
    bytesSaved: number;
    usedLookupTables: string[];
}
export declare function compileLegacyTransactionToV0({ transaction, lookupTables, }: CompileLegacyTransactionToV0Input): CompileLegacyTransactionToV0Result;
//# sourceMappingURL=lookup-table.d.ts.map