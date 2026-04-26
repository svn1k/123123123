"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.serializeUndelegateArgs = serializeUndelegateArgs;
exports.deserializeUndelegateArgs = deserializeUndelegateArgs;
function serializeUndelegateArgs(args) {
    let requiredSize = 4;
    for (const seed of args.pdaSeeds) {
        requiredSize += 4 + seed.length;
    }
    const buffer = Buffer.alloc(requiredSize);
    let offset = 0;
    buffer.writeUInt32LE(args.pdaSeeds.length, offset);
    offset += 4;
    for (const seed of args.pdaSeeds) {
        buffer.writeUInt32LE(seed.length, offset);
        offset += 4;
        for (const byte of seed) {
            buffer[offset++] = byte;
        }
    }
    return buffer.subarray(0, offset);
}
function deserializeUndelegateArgs(buffer, offset = 0) {
    if (offset + 4 > buffer.length) {
        throw new Error("Buffer underflow: insufficient bytes to read pdaSeeds length");
    }
    const seedsLen = buffer.readUInt32LE(offset);
    offset += 4;
    const pdaSeeds = [];
    for (let i = 0; i < seedsLen; i++) {
        if (offset + 4 > buffer.length) {
            throw new Error(`Buffer underflow: insufficient bytes to read seed ${i} length`);
        }
        const seedLen = buffer.readUInt32LE(offset);
        offset += 4;
        if (offset + seedLen > buffer.length) {
            throw new Error(`Buffer underflow: insufficient bytes to read seed ${i} data (expected ${seedLen} bytes)`);
        }
        const seed = [];
        for (let j = 0; j < seedLen; j++) {
            seed.push(buffer[offset++]);
        }
        pdaSeeds.push(seed);
    }
    return { pdaSeeds };
}
//# sourceMappingURL=undelegateArgs.js.map