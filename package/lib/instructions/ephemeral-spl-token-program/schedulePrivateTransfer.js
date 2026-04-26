"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deriveStashPda = deriveStashPda;
exports.deriveStashAta = deriveStashAta;
exports.deriveHydraCrankPda = deriveHydraCrankPda;
exports.schedulePrivateTransferIx = schedulePrivateTransferIx;
const web3_js_1 = require("@solana/web3.js");
const constants_js_1 = require("../../constants.js");
const crypto_js_1 = require("./crypto.js");
const ephemeralAta_js_1 = require("./ephemeralAta.js");
const transferQueue_js_1 = require("./transferQueue.js");
const SCHEDULE_PRIVATE_TRANSFER_DISCRIMINATOR = 30;
const STASH_PDA_SEED = Buffer.from("stash");
const HYDRA_CRANK_SEED_PREFIX = Buffer.from("crank");
const BUFFER_SEED = Buffer.from("buffer");
const DELEGATION_RECORD_SEED = Buffer.from("delegation");
const DELEGATION_METADATA_SEED = Buffer.from("delegation-metadata");
function deriveStashPda(user, mint) {
    return web3_js_1.PublicKey.findProgramAddressSync([STASH_PDA_SEED, user.toBuffer(), mint.toBuffer()], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
}
function deriveStashAta(user, mint, tokenProgram = constants_js_1.TOKEN_PROGRAM_ID) {
    const [stashPda] = deriveStashPda(user, mint);
    return deriveAtaWithBump(stashPda, mint, tokenProgram);
}
function deriveHydraCrankPda(stashPda, shuttleId) {
    if (!Number.isInteger(shuttleId) ||
        shuttleId < 0 ||
        shuttleId > 4294967295) {
        throw new Error("shuttleId must fit in u32");
    }
    return web3_js_1.PublicKey.findProgramAddressSync([HYDRA_CRANK_SEED_PREFIX, hydraSeed(stashPda, shuttleId)], constants_js_1.HYDRA_PROGRAM_ID);
}
function hydraSeed(stashPda, shuttleId) {
    const seed = Buffer.from(stashPda.toBuffer());
    seed.writeUInt32LE(shuttleId, 0);
    return seed;
}
function schedulePrivateTransferIx(user, mint, shuttleId, destinationOwner, minDelayMs, maxDelayMs, split, validator, tokenProgram = constants_js_1.TOKEN_PROGRAM_ID, clientRefId) {
    if (!Number.isInteger(shuttleId) ||
        shuttleId < 0 ||
        shuttleId > 4294967295) {
        throw new Error("shuttleId must fit in u32");
    }
    if (!Number.isInteger(split) || split <= 0 || split > 4294967295) {
        throw new Error("split must be a positive u32");
    }
    if (minDelayMs < 0n ||
        maxDelayMs < 0n ||
        (clientRefId !== undefined && clientRefId < 0n)) {
        throw new Error("delays and clientRefId must be non-negative");
    }
    if (maxDelayMs < minDelayMs) {
        throw new Error("maxDelayMs must be greater than or equal to minDelayMs");
    }
    const U64_MAX = 0xffffffffffffffffn;
    if (minDelayMs > U64_MAX ||
        maxDelayMs > U64_MAX ||
        (clientRefId !== undefined && clientRefId > U64_MAX)) {
        throw new Error("delays and clientRefId must fit in u64");
    }
    const [stashPda, stashBump] = deriveStashPda(user, mint);
    const [, stashAtaBump] = deriveAtaWithBump(stashPda, mint, tokenProgram);
    const [rentPda] = (0, ephemeralAta_js_1.deriveRentPda)();
    const [shuttleEphemeralAta, shuttleBump] = (0, ephemeralAta_js_1.deriveShuttleEphemeralAta)(stashPda, mint, shuttleId);
    const [shuttleAta, shuttleEataBump] = (0, ephemeralAta_js_1.deriveShuttleAta)(shuttleEphemeralAta, mint);
    const [, shuttleWalletAtaBump] = deriveAtaWithBump(shuttleEphemeralAta, mint, tokenProgram);
    const [, bufferBump] = web3_js_1.PublicKey.findProgramAddressSync([BUFFER_SEED, shuttleAta.toBuffer()], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
    const [, delegationRecordBump] = web3_js_1.PublicKey.findProgramAddressSync([DELEGATION_RECORD_SEED, shuttleAta.toBuffer()], constants_js_1.DELEGATION_PROGRAM_ID);
    const [, delegationMetadataBump] = web3_js_1.PublicKey.findProgramAddressSync([DELEGATION_METADATA_SEED, shuttleAta.toBuffer()], constants_js_1.DELEGATION_PROGRAM_ID);
    const [vault, globalVaultBump] = (0, ephemeralAta_js_1.deriveVault)(mint);
    const [, vaultTokenBump] = deriveAtaWithBump(vault, mint, tokenProgram);
    const [, queueBump] = (0, transferQueue_js_1.deriveTransferQueue)(mint, validator);
    const [hydraCrankPda] = deriveHydraCrankPda(stashPda, shuttleId);
    const encryptedDestination = (0, crypto_js_1.encryptEd25519Recipient)(destinationOwner.toBytes(), validator);
    const encryptedSuffix = (0, crypto_js_1.encryptEd25519Recipient)(packPrivateTransferSuffix(minDelayMs, maxDelayMs, split, clientRefId), validator);
    const data = Buffer.concat([
        Buffer.from([SCHEDULE_PRIVATE_TRANSFER_DISCRIMINATOR]),
        u32leBuffer(shuttleId),
        Buffer.from([stashBump]),
        mint.toBuffer(),
        Buffer.from([shuttleBump]),
        Buffer.from([shuttleEataBump]),
        Buffer.from([shuttleWalletAtaBump]),
        Buffer.from([bufferBump]),
        Buffer.from([delegationRecordBump]),
        Buffer.from([delegationMetadataBump]),
        Buffer.from([globalVaultBump]),
        Buffer.from([vaultTokenBump]),
        Buffer.from([stashAtaBump]),
        Buffer.from([queueBump]),
        encodeLengthPrefixedBytes(validator.toBytes()),
        encodeLengthPrefixedBytes(encryptedDestination),
        encodeLengthPrefixedBytes(encryptedSuffix),
    ]);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: user, isSigner: true, isWritable: true },
            { pubkey: stashPda, isSigner: false, isWritable: true },
            { pubkey: rentPda, isSigner: false, isWritable: true },
            { pubkey: hydraCrankPda, isSigner: false, isWritable: true },
            { pubkey: constants_js_1.HYDRA_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
            { pubkey: tokenProgram, isSigner: false, isWritable: false },
        ],
        data,
    });
}
function deriveAtaWithBump(wallet, mint, tokenProgram) {
    return web3_js_1.PublicKey.findProgramAddressSync([wallet.toBuffer(), tokenProgram.toBuffer(), mint.toBuffer()], constants_js_1.ASSOCIATED_TOKEN_PROGRAM_ID);
}
function encodeLengthPrefixedBytes(bytes) {
    if (bytes.length > 0xff) {
        throw new Error("payload exceeds u8 length");
    }
    return Buffer.concat([Buffer.from([bytes.length]), Buffer.from(bytes)]);
}
function packPrivateTransferSuffix(minDelayMs, maxDelayMs, split, clientRefId) {
    const suffix = Buffer.alloc(clientRefId === undefined ? 8 + 8 + 4 : 8 + 8 + 4 + 8);
    suffix.writeBigUInt64LE(minDelayMs, 0);
    suffix.writeBigUInt64LE(maxDelayMs, 8);
    suffix.writeUInt32LE(split, 16);
    if (clientRefId !== undefined) {
        suffix.writeBigUInt64LE(clientRefId, 20);
    }
    return suffix;
}
function u32leBuffer(value) {
    const out = Buffer.alloc(4);
    out.writeUInt32LE(value, 0);
    return out;
}
//# sourceMappingURL=schedulePrivateTransfer.js.map