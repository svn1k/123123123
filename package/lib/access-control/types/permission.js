"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.serializePermission = serializePermission;
exports.deserializePermission = deserializePermission;
const web3_js_1 = require("@solana/web3.js");
const member_1 = require("./member");
function serializePermission(permission) {
    const buffer = Buffer.alloc(567);
    let offset = 0;
    buffer[offset++] = permission.discriminator;
    buffer[offset++] = permission.bump;
    buffer.set(permission.permissionedAccount.toBuffer(), offset);
    offset += 32;
    if (permission.members !== undefined) {
        buffer[offset++] = 1;
        buffer.writeUInt32LE(permission.members?.length ?? 0, offset);
        offset += 4;
        for (const member of permission.members ?? []) {
            const memberBuffer = (0, member_1.serializeMember)(member);
            buffer.set(memberBuffer, offset);
            offset += member_1.MEMBER_SIZE;
        }
    }
    else {
        buffer[offset++] = 0;
    }
    return buffer.subarray(0, offset);
}
function deserializePermission(buffer, offset = 0) {
    const discriminator = buffer[offset];
    offset += 1;
    const bump = buffer[offset];
    offset += 1;
    const permissionedAccount = new web3_js_1.PublicKey(buffer.subarray(offset, offset + 32));
    offset += 32;
    let members;
    const hasMembers = buffer[offset++];
    if (hasMembers) {
        const membersCount = buffer.readUInt32LE(offset);
        offset += 4;
        members = [];
        for (let i = 0; i < membersCount; i++) {
            members.push((0, member_1.deserializeMember)(buffer.subarray(offset)));
            offset += 33;
        }
    }
    return { discriminator, bump, permissionedAccount, members };
}
//# sourceMappingURL=permission.js.map