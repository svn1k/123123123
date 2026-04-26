"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createCommitAndUndelegatePermissionInstruction = createCommitAndUndelegatePermissionInstruction;
exports.serializeCommitAndUndelegatePermissionInstructionData = serializeCommitAndUndelegatePermissionInstructionData;
const web3_js_1 = require("@solana/web3.js");
const constants_1 = require("../../constants");
const pda_1 = require("../../pda");
function createCommitAndUndelegatePermissionInstruction(accounts) {
    const permission = (0, pda_1.permissionPdaFromAccount)(accounts.permissionedAccount[0]);
    const keys = [
        {
            pubkey: accounts.authority[0],
            isWritable: accounts.authority[1],
            isSigner: accounts.authority[1],
        },
        {
            pubkey: accounts.permissionedAccount[0],
            isWritable: true,
            isSigner: accounts.permissionedAccount[1],
        },
        { pubkey: permission, isWritable: true, isSigner: false },
        { pubkey: constants_1.MAGIC_PROGRAM_ID, isWritable: false, isSigner: false },
        { pubkey: constants_1.MAGIC_CONTEXT_ID, isWritable: true, isSigner: false },
    ];
    const instructionData = serializeCommitAndUndelegatePermissionInstructionData();
    return new web3_js_1.TransactionInstruction({
        programId: constants_1.PERMISSION_PROGRAM_ID,
        keys,
        data: instructionData,
    });
}
function serializeCommitAndUndelegatePermissionInstructionData() {
    const discriminator = [5, 0, 0, 0, 0, 0, 0, 0];
    const buffer = Buffer.alloc(8);
    for (let i = 0; i < 8; i++) {
        buffer[i] = discriminator[i];
    }
    return buffer;
}
//# sourceMappingURL=commitAndUndelegatePermission.js.map