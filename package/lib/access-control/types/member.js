"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ACCOUNT_SIGNATURES_FLAG = exports.TX_MESSAGE_FLAG = exports.TX_BALANCES_FLAG = exports.TX_LOGS_FLAG = exports.AUTHORITY_FLAG = exports.MEMBER_SIZE = void 0;
exports.serializeMember = serializeMember;
exports.deserializeMember = deserializeMember;
exports.isAuthority = isAuthority;
exports.canSeeTxLogs = canSeeTxLogs;
exports.canSeeTxBalances = canSeeTxBalances;
exports.canSeeTxMessages = canSeeTxMessages;
exports.canSeeAccountSignatures = canSeeAccountSignatures;
const web3_js_1 = require("@solana/web3.js");
exports.MEMBER_SIZE = 33;
exports.AUTHORITY_FLAG = 1 << 0;
exports.TX_LOGS_FLAG = 1 << 1;
exports.TX_BALANCES_FLAG = 1 << 2;
exports.TX_MESSAGE_FLAG = 1 << 3;
exports.ACCOUNT_SIGNATURES_FLAG = 1 << 4;
function serializeMember(member) {
    const buffer = Buffer.alloc(exports.MEMBER_SIZE);
    let offset = 0;
    buffer[offset++] = member.flags;
    buffer.set(member.pubkey.toBuffer(), offset);
    offset += 32;
    return buffer.subarray(0, offset);
}
function deserializeMember(buffer, offset = 0) {
    const flags = buffer[offset];
    offset += 1;
    const pubkey = new web3_js_1.PublicKey(buffer.subarray(offset, offset + 32));
    offset += 32;
    return { flags, pubkey };
}
function isAuthority(member, user) {
    return (member.flags & exports.AUTHORITY_FLAG) !== 0 && member.pubkey.equals(user);
}
function canSeeTxLogs(member, user) {
    return (member.flags & exports.TX_LOGS_FLAG) !== 0 && member.pubkey.equals(user);
}
function canSeeTxBalances(member, user) {
    return (member.flags & exports.TX_BALANCES_FLAG) !== 0 && member.pubkey.equals(user);
}
function canSeeTxMessages(member, user) {
    return (member.flags & exports.TX_MESSAGE_FLAG) !== 0 && member.pubkey.equals(user);
}
function canSeeAccountSignatures(member, user) {
    return ((member.flags & exports.ACCOUNT_SIGNATURES_FLAG) !== 0 && member.pubkey.equals(user));
}
//# sourceMappingURL=member.js.map