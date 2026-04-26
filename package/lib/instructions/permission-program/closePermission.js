"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createClosePermissionInstruction = createClosePermissionInstruction;
exports.serializeClosePermissionInstructionData = serializeClosePermissionInstructionData;
const web3_js_1 = require("@solana/web3.js");
const constants_1 = require("../../constants");
const pda_1 = require("../../pda");
function createClosePermissionInstruction(accounts) {
    const permission = (0, pda_1.permissionPdaFromAccount)(accounts.permissionedAccount[0]);
    const keys = [
        { pubkey: accounts.payer, isWritable: true, isSigner: false },
        {
            pubkey: accounts.authority[0],
            isWritable: false,
            isSigner: accounts.authority[1],
        },
        {
            pubkey: accounts.permissionedAccount[0],
            isWritable: false,
            isSigner: accounts.permissionedAccount[1],
        },
        { pubkey: permission, isWritable: true, isSigner: false },
    ];
    const instructionData = serializeClosePermissionInstructionData();
    return new web3_js_1.TransactionInstruction({
        programId: constants_1.PERMISSION_PROGRAM_ID,
        keys,
        data: instructionData,
    });
}
function serializeClosePermissionInstructionData() {
    const discriminator = [2, 0, 0, 0, 0, 0, 0, 0];
    const buffer = Buffer.alloc(8);
    for (let i = 0; i < 8; i++) {
        buffer[i] = discriminator[i];
    }
    return buffer;
}
//# sourceMappingURL=closePermission.js.map