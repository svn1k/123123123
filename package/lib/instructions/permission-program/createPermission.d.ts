import { PublicKey, TransactionInstruction } from "@solana/web3.js";
import { type MembersArgs } from "../../access-control/types";
export declare const CREATE_PERMISSION_DISCRIMINATOR: number[];
export declare function createCreatePermissionInstruction(accounts: {
    permissionedAccount: PublicKey;
    payer: PublicKey;
}, args: MembersArgs): TransactionInstruction;
//# sourceMappingURL=createPermission.d.ts.map