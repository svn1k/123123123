import { PublicKey, TransactionInstruction } from "@solana/web3.js";
export interface DelegatePermissionInstructionArgs {
    validator?: PublicKey | null;
}
export declare function createDelegatePermissionInstruction(accounts: {
    payer: PublicKey;
    authority: [PublicKey, boolean];
    permissionedAccount: [PublicKey, boolean];
    ownerProgram?: PublicKey;
    validator?: PublicKey | null;
}, args?: DelegatePermissionInstructionArgs): TransactionInstruction;
export declare function serializeDelegatePermissionInstructionData(): Buffer;
//# sourceMappingURL=delegatePermission.d.ts.map