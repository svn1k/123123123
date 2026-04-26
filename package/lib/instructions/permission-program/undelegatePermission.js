"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.createUndelegatePermissionInstruction = createUndelegatePermissionInstruction;
exports.serializeUndelegatePermissionInstructionData = serializeUndelegatePermissionInstructionData;
const web3_js_1 = require("@solana/web3.js");
const constants_1 = require("../../constants");
function createUndelegatePermissionInstruction(accounts, args) {
    const keys = [
        { pubkey: accounts.delegatedPermission, isWritable: true, isSigner: false },
        { pubkey: accounts.delegationBuffer, isWritable: true, isSigner: false },
        { pubkey: accounts.validator, isWritable: false, isSigner: true },
        { pubkey: web3_js_1.SystemProgram.programId, isWritable: false, isSigner: false },
    ];
    const instructionData = serializeUndelegatePermissionInstructionData(args);
    return new web3_js_1.TransactionInstruction({
        programId: constants_1.PERMISSION_PROGRAM_ID,
        keys,
        data: instructionData,
    });
}
function serializeUndelegatePermissionInstructionData(args) {
    const MAX_SEED_LENGTH = 32;
    const discriminator = [0xa4, 0xa7, 0x5c, 0xcc, 0x04, 0x8a, 0xa9, 0xa6];
    const pdaSeeds = args?.pdaSeeds ?? [];
    for (let i = 0; i < pdaSeeds.length; i++) {
        if (pdaSeeds[i].length > MAX_SEED_LENGTH) {
            throw new Error(`PDA seed ${i} exceeds maximum length of ${MAX_SEED_LENGTH} bytes (got ${pdaSeeds[i].length})`);
        }
    }
    let requiredSize = 8 + 4;
    for (const seed of pdaSeeds) {
        requiredSize += 4 + seed.length;
    }
    const buffer = Buffer.alloc(requiredSize);
    let offset = 0;
    for (let i = 0; i < 8; i++) {
        buffer[offset++] = discriminator[i];
    }
    buffer.writeUInt32LE(pdaSeeds.length, offset);
    offset += 4;
    for (const seed of pdaSeeds) {
        buffer.writeUInt32LE(seed.length, offset);
        offset += 4;
        buffer.set(seed, offset);
        offset += seed.length;
    }
    return buffer;
}
//# sourceMappingURL=undelegatePermission.js.map