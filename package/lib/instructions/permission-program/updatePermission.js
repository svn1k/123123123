"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.UPDATE_PERMISSION_DISCRIMINATOR = void 0;
exports.createUpdatePermissionInstruction = createUpdatePermissionInstruction;
const web3_js_1 = require("@solana/web3.js");
const constants_1 = require("../../constants");
const pda_1 = require("../../pda");
const types_1 = require("../../access-control/types");
exports.UPDATE_PERMISSION_DISCRIMINATOR = [1, 0, 0, 0, 0, 0, 0, 0];
function createUpdatePermissionInstruction(accounts, args) {
    const permission = (0, pda_1.permissionPdaFromAccount)(accounts.permissionedAccount[0]);
    const keys = [
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
    const argsBuffer = (0, types_1.serializeMembersArgs)(args);
    const instructionData = Buffer.from([
        ...exports.UPDATE_PERMISSION_DISCRIMINATOR,
        ...argsBuffer,
    ]);
    return new web3_js_1.TransactionInstruction({
        programId: constants_1.PERMISSION_PROGRAM_ID,
        keys,
        data: instructionData,
    });
}
//# sourceMappingURL=updatePermission.js.map