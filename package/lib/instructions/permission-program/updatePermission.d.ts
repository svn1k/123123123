import { PublicKey, TransactionInstruction } from "@solana/web3.js";
import { type MembersArgs } from "../../access-control/types";
export declare const UPDATE_PERMISSION_DISCRIMINATOR: number[];
export declare function createUpdatePermissionInstruction(accounts: {
    authority: [PublicKey, boolean];
    permissionedAccount: [PublicKey, boolean];
}, args: MembersArgs): TransactionInstruction;
//# sourceMappingURL=updatePermission.d.ts.map