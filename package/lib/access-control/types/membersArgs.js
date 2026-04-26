"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.serializeMembersArgs = serializeMembersArgs;
exports.deserializeMembersArgs = deserializeMembersArgs;
const member_1 = require("./member");
function serializeMembersArgs(args) {
    let requiredSize = 1;
    if (args.members !== null) {
        requiredSize += 4 + args.members.length * member_1.MEMBER_SIZE;
    }
    const buffer = Buffer.alloc(requiredSize);
    let offset = 0;
    if (args.members === null) {
        buffer[offset++] = 0;
        return buffer.subarray(0, offset);
    }
    buffer[offset++] = 1;
    buffer.writeUInt32LE(args.members.length, offset);
    offset += 4;
    for (const member of args.members) {
        const memberBuffer = (0, member_1.serializeMember)(member);
        if (memberBuffer.length !== member_1.MEMBER_SIZE) {
            throw new Error(`Member serialization mismatch: expected ${member_1.MEMBER_SIZE} bytes, got ${memberBuffer.length}`);
        }
        buffer.set(memberBuffer, offset);
        offset += member_1.MEMBER_SIZE;
    }
    return buffer.subarray(0, offset);
}
function deserializeMembersArgs(buffer, offset = 0) {
    if (offset + 1 > buffer.length) {
        throw new Error("Buffer underflow: insufficient bytes to read members discriminant");
    }
    const discriminant = buffer[offset++];
    let members = null;
    if (discriminant === 0) {
        members = null;
    }
    else if (discriminant === 1) {
        if (offset + 4 > buffer.length) {
            throw new Error("Buffer underflow: insufficient bytes to read members length");
        }
        const len = buffer.readUInt32LE(offset);
        offset += 4;
        members = [];
        for (let i = 0; i < len; i++) {
            if (offset + member_1.MEMBER_SIZE > buffer.length) {
                throw new Error(`Buffer underflow: insufficient bytes to read member ${i} (expected ${member_1.MEMBER_SIZE} bytes)`);
            }
            const member = (0, member_1.deserializeMember)(buffer, offset);
            members.push(member);
            offset += member_1.MEMBER_SIZE;
        }
    }
    else {
        throw new Error(`Invalid discriminant for MembersArgs: expected 0 (None) or 1 (Some), got ${discriminant}`);
    }
    return { members };
}
//# sourceMappingURL=membersArgs.js.map