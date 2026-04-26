import { PublicKey } from "@solana/web3.js";
import { Member } from "./member";
export interface Permission {
    discriminator: number;
    bump: number;
    permissionedAccount: PublicKey;
    members?: Member[];
}
export declare function serializePermission(permission: Permission): Buffer;
export declare function deserializePermission(buffer: Buffer, offset?: number): Permission;
//# sourceMappingURL=permission.d.ts.map