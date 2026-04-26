import { PublicKey, TransactionInstruction } from "@solana/web3.js";
export declare function createClosePermissionInstruction(accounts: {
    payer: PublicKey;
    authority: [PublicKey, boolean];
    permissionedAccount: [PublicKey, boolean];
}): TransactionInstruction;
export declare function serializeClosePermissionInstructionData(): Buffer;
//# sourceMappingURL=closePermission.d.ts.map