import { PublicKey } from "@solana/web3.js";
export declare const MEMBER_SIZE = 33;
export declare const AUTHORITY_FLAG: number;
export declare const TX_LOGS_FLAG: number;
export declare const TX_BALANCES_FLAG: number;
export declare const TX_MESSAGE_FLAG: number;
export declare const ACCOUNT_SIGNATURES_FLAG: number;
export interface Member {
    flags: number;
    pubkey: PublicKey;
}
export declare function serializeMember(member: Member): Buffer;
export declare function deserializeMember(buffer: Buffer, offset?: number): Member;
export declare function isAuthority(member: Member, user: PublicKey): boolean;
export declare function canSeeTxLogs(member: Member, user: PublicKey): boolean;
export declare function canSeeTxBalances(member: Member, user: PublicKey): boolean;
export declare function canSeeTxMessages(member: Member, user: PublicKey): boolean;
export declare function canSeeAccountSignatures(member: Member, user: PublicKey): boolean;
//# sourceMappingURL=member.d.ts.map