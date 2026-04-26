import { PublicKey, TransactionInstruction, AccountInfo } from "@solana/web3.js";
export interface EphemeralAta {
    owner: PublicKey;
    mint: PublicKey;
    amount: bigint;
}
export declare function decodeEphemeralAta(info: AccountInfo<Buffer>): EphemeralAta;
export declare function encodeEphemeralAta(eata: EphemeralAta): Buffer;
export interface GlobalVault {
    mint: PublicKey;
}
export declare function decodeGlobalVault(info: AccountInfo<Buffer>): GlobalVault;
export declare function encodeGlobalVault(vault: GlobalVault): Buffer;
export declare function deriveEphemeralAta(owner: PublicKey, mint: PublicKey): [PublicKey, number];
export declare function deriveVault(mint: PublicKey): [PublicKey, number];
export declare function deriveRentPda(): [PublicKey, number];
export declare function deriveLamportsPda(payer: PublicKey, destination: PublicKey, salt: Uint8Array): [PublicKey, number];
export declare function deriveVaultAta(mint: PublicKey, vault: PublicKey): PublicKey;
export declare function deriveShuttleEphemeralAta(owner: PublicKey, mint: PublicKey, shuttleId: number): [PublicKey, number];
export declare function deriveShuttleAta(shuttleEphemeralAta: PublicKey, mint: PublicKey): [PublicKey, number];
export declare function deriveShuttleWalletAta(mint: PublicKey, shuttleEphemeralAta: PublicKey): PublicKey;
export declare function initEphemeralAtaIx(ephemeralAta: PublicKey, owner: PublicKey, mint: PublicKey, payer: PublicKey): TransactionInstruction;
export declare function initVaultAtaIx(payer: PublicKey, vaultAta: PublicKey, vault: PublicKey, mint: PublicKey): TransactionInstruction;
export declare function initVaultIx(vault: PublicKey, mint: PublicKey, payer: PublicKey): TransactionInstruction;
export declare function initRentPdaIx(payer: PublicKey, rentPda: PublicKey): TransactionInstruction;
export declare function transferToVaultIx(ephemeralAta: PublicKey, vault: PublicKey, mint: PublicKey, sourceAta: PublicKey, vaultAta: PublicKey, owner: PublicKey, amount: bigint): TransactionInstruction;
export declare function depositSplTokensIx(ephemeralAta: PublicKey, vault: PublicKey, mint: PublicKey, sourceAta: PublicKey, vaultAta: PublicKey, owner: PublicKey, amount: bigint): TransactionInstruction;
export declare function delegateEphemeralAtaIx(payer: PublicKey, ephemeralAta: PublicKey, validator?: PublicKey): TransactionInstruction;
export declare function initShuttleEphemeralAtaIx(payer: PublicKey, shuttleEphemeralAta: PublicKey, shuttleAta: PublicKey, shuttleWalletAta: PublicKey, owner: PublicKey, mint: PublicKey, shuttleId: number): TransactionInstruction;
export declare function delegateShuttleEphemeralAtaIx(payer: PublicKey, shuttleEphemeralAta: PublicKey, shuttleAta: PublicKey, validator?: PublicKey): TransactionInstruction;
export declare function setupAndDelegateShuttleEphemeralAtaWithMergeIx(payer: PublicKey, shuttleEphemeralAta: PublicKey, shuttleAta: PublicKey, owner: PublicKey, sourceAta: PublicKey, destinationAta: PublicKey, shuttleWalletAta: PublicKey, mint: PublicKey, shuttleId: number, amount: bigint, validator?: PublicKey): TransactionInstruction;
export declare function depositAndDelegateShuttleEphemeralAtaWithMergeAndPrivateTransferIx(payer: PublicKey, shuttleEphemeralAta: PublicKey, shuttleAta: PublicKey, owner: PublicKey, sourceAta: PublicKey, destinationOwner: PublicKey, shuttleWalletAta: PublicKey, mint: PublicKey, shuttleId: number, amount: bigint, minDelayMs: bigint, maxDelayMs: bigint, split: number, validator?: PublicKey, clientRefId?: bigint): TransactionInstruction;
export declare function withdrawThroughDelegatedShuttleWithMergeIx(payer: PublicKey, shuttleEphemeralAta: PublicKey, shuttleAta: PublicKey, owner: PublicKey, ownerAta: PublicKey, shuttleWalletAta: PublicKey, mint: PublicKey, shuttleId: number, amount: bigint, validator?: PublicKey): TransactionInstruction;
export declare function lamportsDelegatedTransferIx(payer: PublicKey, destination: PublicKey, amount: bigint, salt: Uint8Array): TransactionInstruction;
export declare function mergeShuttleIntoAtaIx(owner: PublicKey, destinationAta: PublicKey, shuttleEphemeralAta: PublicKey, shuttleWalletAta: PublicKey, mint: PublicKey): TransactionInstruction;
export declare function undelegateAndCloseShuttleEphemeralAtaIx(payer: PublicKey, rentReimbursement: PublicKey, shuttleEphemeralAta: PublicKey, shuttleAta: PublicKey, shuttleWalletAta: PublicKey, destinationAta: PublicKey, escrowIndex?: number): TransactionInstruction;
export declare function withdrawSplIx(owner: PublicKey, mint: PublicKey, amount: bigint): TransactionInstruction;
export declare function undelegateIx(owner: PublicKey, mint: PublicKey): TransactionInstruction;
export declare function createEataPermissionIx(ephemeralAta: PublicKey, payer: PublicKey, flags?: number): TransactionInstruction;
export declare function resetEataPermissionIx(ephemeralAta: PublicKey, payer: PublicKey, flags?: number): TransactionInstruction;
export declare function delegateEataPermissionIx(payer: PublicKey, ephemeralAta: PublicKey, validator: PublicKey): TransactionInstruction;
export declare function undelegateEataPermissionIx(owner: PublicKey, ephemeralAta: PublicKey): TransactionInstruction;
export interface DelegateSplOptions {
    payer?: PublicKey;
    validator?: PublicKey;
    initIfMissing?: boolean;
    initVaultIfMissing?: boolean;
    initAtasIfMissing?: boolean;
    shuttleId?: number;
    escrowIndex?: number;
    idempotent?: boolean;
    private?: boolean;
}
export interface DelegateSplWithPrivateTransferOptions extends Omit<DelegateSplOptions, "private"> {
    minDelayMs?: bigint;
    maxDelayMs?: bigint;
    split?: number;
    clientRefId?: bigint;
    initTransferQueueIfMissing?: boolean;
}
export interface WithdrawSplOptions extends Omit<DelegateSplOptions, "private" | "initVaultIfMissing"> {
}
export type TransferBalance = "base" | "ephemeral";
export type TransferVisibility = "public" | "private";
export interface TransferSplPrivateOptions {
    minDelayMs?: bigint;
    maxDelayMs?: bigint;
    split?: number;
    clientRefId?: bigint;
}
export interface TransferSplOptions {
    visibility: TransferVisibility;
    fromBalance: TransferBalance;
    toBalance: TransferBalance;
    payer?: PublicKey;
    validator?: PublicKey;
    initIfMissing?: boolean;
    initAtasIfMissing?: boolean;
    initVaultIfMissing?: boolean;
    shuttleId?: number;
    privateTransfer?: TransferSplPrivateOptions;
}
export declare function delegateSpl(owner: PublicKey, mint: PublicKey, amount: bigint, opts?: DelegateSplOptions): Promise<TransactionInstruction[]>;
export declare function delegateSplWithPrivateTransfer(owner: PublicKey, mint: PublicKey, amount: bigint, opts?: DelegateSplWithPrivateTransferOptions): Promise<TransactionInstruction[]>;
export declare function transferSpl(from: PublicKey, to: PublicKey, mint: PublicKey, amount: bigint, opts: TransferSplOptions): Promise<TransactionInstruction[]>;
export declare function withdrawSpl(owner: PublicKey, mint: PublicKey, amount: bigint, opts?: WithdrawSplOptions): Promise<TransactionInstruction[]>;
//# sourceMappingURL=ephemeralAta.d.ts.map