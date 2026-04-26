"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createDelegatePermissionInstruction = createDelegatePermissionInstruction;
exports.serializeDelegatePermissionInstructionData = serializeDelegatePermissionInstructionData;
const web3_js_1 = require("@solana/web3.js");
const constants_1 = require("../../constants");
const pda_1 = require("../../pda");
function createDelegatePermissionInstruction(accounts, args) {
    const ownerProgram = accounts.ownerProgram ?? constants_1.PERMISSION_PROGRAM_ID;
    const permissionPda = (0, pda_1.permissionPdaFromAccount)(accounts.permissionedAccount[0]);
    const delegateBuffer = (0, pda_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(permissionPda, ownerProgram);
    const delegationRecord = (0, pda_1.delegationRecordPdaFromDelegatedAccount)(permissionPda);
    const delegationMetadata = (0, pda_1.delegationMetadataPdaFromDelegatedAccount)(permissionPda);
    const validator = args?.validator ?? accounts.validator;
    const keys = [
        { pubkey: accounts.payer, isWritable: true, isSigner: true },
        {
            pubkey: accounts.authority[0],
            isWritable: accounts.authority[1],
            isSigner: accounts.authority[1],
        },
        {
            pubkey: accounts.permissionedAccount[0],
            isWritable: accounts.permissionedAccount[1],
            isSigner: accounts.permissionedAccount[1],
        },
        { pubkey: permissionPda, isWritable: true, isSigner: false },
        { pubkey: web3_js_1.SystemProgram.programId, isWritable: false, isSigner: false },
        { pubkey: ownerProgram, isWritable: false, isSigner: false },
        { pubkey: delegateBuffer, isWritable: true, isSigner: false },
        { pubkey: delegationRecord, isWritable: true, isSigner: false },
        { pubkey: delegationMetadata, isWritable: true, isSigner: false },
        { pubkey: constants_1.DELEGATION_PROGRAM_ID, isWritable: false, isSigner: false },
    ];
    if (validator) {
        keys.push({
            pubkey: validator,
            isWritable: false,
            isSigner: false,
        });
    }
    const instructionData = serializeDelegatePermissionInstructionData();
    return new web3_js_1.TransactionInstruction({
        programId: constants_1.PERMISSION_PROGRAM_ID,
        keys,
        data: instructionData,
    });
}
function serializeDelegatePermissionInstructionData() {
    const discriminator = [3, 0, 0, 0, 0, 0, 0, 0];
    const buffer = Buffer.alloc(8);
    for (let i = 0; i < 8; i++) {
        buffer[i] = discriminator[i];
    }
    return buffer;
}
//# sourceMappingURL=delegatePermission.js.map