"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CREATE_PERMISSION_DISCRIMINATOR = void 0;
exports.createCreatePermissionInstruction = createCreatePermissionInstruction;
const web3_js_1 = require("@solana/web3.js");
const constants_1 = require("../../constants");
const pda_1 = require("../../pda");
const types_1 = require("../../access-control/types");
exports.CREATE_PERMISSION_DISCRIMINATOR = [0, 0, 0, 0, 0, 0, 0, 0];
function createCreatePermissionInstruction(accounts, args) {
    const permission = (0, pda_1.permissionPdaFromAccount)(accounts.permissionedAccount);
    const keys = [
        { pubkey: accounts.permissionedAccount, isWritable: false, isSigner: true },
        { pubkey: permission, isWritable: true, isSigner: false },
        { pubkey: accounts.payer, isWritable: true, isSigner: true },
        { pubkey: web3_js_1.SystemProgram.programId, isWritable: false, isSigner: false },
    ];
    const argsBuffer = (0, types_1.serializeMembersArgs)(args);
    const instructionData = Buffer.from([
        ...exports.CREATE_PERMISSION_DISCRIMINATOR,
        ...argsBuffer,
    ]);
    return new web3_js_1.TransactionInstruction({
        programId: constants_1.PERMISSION_PROGRAM_ID,
        keys,
        data: instructionData,
    });
}
//# sourceMappingURL=createPermission.js.map