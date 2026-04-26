import { PublicKey, TransactionInstruction } from "@solana/web3.js";
export declare function deriveStashPda(user: PublicKey, mint: PublicKey): [PublicKey, number];
export declare function deriveStashAta(user: PublicKey, mint: PublicKey, tokenProgram?: PublicKey): [PublicKey, number];
export declare function deriveHydraCrankPda(stashPda: PublicKey, shuttleId: number): [PublicKey, number];
export declare function schedulePrivateTransferIx(user: PublicKey, mint: PublicKey, shuttleId: number, destinationOwner: PublicKey, minDelayMs: bigint, maxDelayMs: bigint, split: number, validator: PublicKey, tokenProgram?: PublicKey, clientRefId?: bigint): TransactionInstruction;
//# sourceMappingURL=schedulePrivateTransfer.d.ts.map