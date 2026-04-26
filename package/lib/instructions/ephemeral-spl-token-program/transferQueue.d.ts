import { AccountMeta, PublicKey, TransactionInstruction } from "@solana/web3.js";
export interface StructuredInstruction {
    accounts: AccountMeta[];
    data: Uint8Array;
    programAddress: PublicKey;
}
export declare function toTransactionInstruction(instruction: StructuredInstruction | TransactionInstruction): TransactionInstruction;
export declare function deriveTransferQueue(mint: PublicKey, validator: PublicKey): [PublicKey, number];
export declare function initTransferQueueIx(payer: PublicKey, queue: PublicKey, mint: PublicKey, validator: PublicKey, requestedItems?: number): TransactionInstruction;
export declare function allocateTransferQueueIx(queue: PublicKey): TransactionInstruction;
export declare function depositAndQueueTransferIx(queue: PublicKey, vault: PublicKey, mint: PublicKey, source: PublicKey, vaultAta: PublicKey, destination: PublicKey, owner: PublicKey, amount: bigint, minDelayMs?: bigint, maxDelayMs?: bigint, split?: number, reimbursementTokenInfo?: PublicKey, clientRefId?: bigint): TransactionInstruction;
export declare function ensureTransferQueueCrankIx(payer: PublicKey, queue: PublicKey, magicFeeVault: PublicKey, magicContext?: PublicKey, magicProgram?: PublicKey): TransactionInstruction;
export declare function delegateTransferQueueIx(queue: PublicKey, payer: PublicKey, mint: PublicKey): TransactionInstruction;
export declare function processPendingTransferQueueRefillIx(queue: PublicKey): TransactionInstruction;
//# sourceMappingURL=transferQueue.d.ts.map