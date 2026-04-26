import { type Member } from "./member";
export interface MembersArgs {
    members: Member[] | null;
}
export declare function serializeMembersArgs(args: MembersArgs): Buffer;
export declare function deserializeMembersArgs(buffer: Buffer, offset?: number): MembersArgs;
//# sourceMappingURL=membersArgs.d.ts.map