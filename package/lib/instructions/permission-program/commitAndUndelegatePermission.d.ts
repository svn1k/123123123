import { PublicKey, TransactionInstruction } from "@solana/web3.js";
export declare function createCommitAndUndelegatePermissionInstruction(accounts: {
    authority: [PublicKey, boolean];
    permissionedAccount: [PublicKey, boolean];
}): TransactionInstruction;
export declare function serializeCommitAndUndelegatePermissionInstructionData(): Buffer;
//# sourceMappingURL=commitAndUndelegatePermission.d.ts.map