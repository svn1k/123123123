import { PublicKey, TransactionInstruction } from "@solana/web3.js";
export declare function createCommitPermissionInstruction(accounts: {
    authority: [PublicKey, boolean];
    permissionedAccount: [PublicKey, boolean];
}): TransactionInstruction;
export declare function serializeCommitPermissionInstructionData(): Buffer;
//# sourceMappingURL=commitPermission.d.ts.map