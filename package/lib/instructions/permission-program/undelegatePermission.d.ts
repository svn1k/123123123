import { PublicKey, TransactionInstruction } from "@solana/web3.js";
export interface UndelegatePermissionInstructionArgs {
    pdaSeeds?: Uint8Array[];
}
export declare function createUndelegatePermissionInstruction(accounts: {
    delegatedPermission: PublicKey;
    delegationBuffer: PublicKey;
    validator: PublicKey;
}, args?: UndelegatePermissionInstructionArgs): TransactionInstruction;
export declare function serializeUndelegatePermissionInstructionData(args?: UndelegatePermissionInstructionArgs): Buffer;
//# sourceMappingURL=undelegatePermission.d.ts.map