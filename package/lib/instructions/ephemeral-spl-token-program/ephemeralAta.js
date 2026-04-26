"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.decodeEphemeralAta = decodeEphemeralAta;
exports.encodeEphemeralAta = encodeEphemeralAta;
exports.decodeGlobalVault = decodeGlobalVault;
exports.encodeGlobalVault = encodeGlobalVault;
exports.deriveEphemeralAta = deriveEphemeralAta;
exports.deriveVault = deriveVault;
exports.deriveRentPda = deriveRentPda;
exports.deriveLamportsPda = deriveLamportsPda;
exports.deriveVaultAta = deriveVaultAta;
exports.deriveShuttleEphemeralAta = deriveShuttleEphemeralAta;
exports.deriveShuttleAta = deriveShuttleAta;
exports.deriveShuttleWalletAta = deriveShuttleWalletAta;
exports.initEphemeralAtaIx = initEphemeralAtaIx;
exports.initVaultAtaIx = initVaultAtaIx;
exports.initVaultIx = initVaultIx;
exports.initRentPdaIx = initRentPdaIx;
exports.transferToVaultIx = transferToVaultIx;
exports.depositSplTokensIx = depositSplTokensIx;
exports.delegateEphemeralAtaIx = delegateEphemeralAtaIx;
exports.initShuttleEphemeralAtaIx = initShuttleEphemeralAtaIx;
exports.delegateShuttleEphemeralAtaIx = delegateShuttleEphemeralAtaIx;
exports.setupAndDelegateShuttleEphemeralAtaWithMergeIx = setupAndDelegateShuttleEphemeralAtaWithMergeIx;
exports.depositAndDelegateShuttleEphemeralAtaWithMergeAndPrivateTransferIx = depositAndDelegateShuttleEphemeralAtaWithMergeAndPrivateTransferIx;
exports.withdrawThroughDelegatedShuttleWithMergeIx = withdrawThroughDelegatedShuttleWithMergeIx;
exports.lamportsDelegatedTransferIx = lamportsDelegatedTransferIx;
exports.mergeShuttleIntoAtaIx = mergeShuttleIntoAtaIx;
exports.undelegateAndCloseShuttleEphemeralAtaIx = undelegateAndCloseShuttleEphemeralAtaIx;
exports.withdrawSplIx = withdrawSplIx;
exports.undelegateIx = undelegateIx;
exports.createEataPermissionIx = createEataPermissionIx;
exports.resetEataPermissionIx = resetEataPermissionIx;
exports.delegateEataPermissionIx = delegateEataPermissionIx;
exports.undelegateEataPermissionIx = undelegateEataPermissionIx;
exports.delegateSpl = delegateSpl;
exports.delegateSplWithPrivateTransfer = delegateSplWithPrivateTransfer;
exports.transferSpl = transferSpl;
exports.withdrawSpl = withdrawSpl;
const web3_js_1 = require("@solana/web3.js");
const constants_js_1 = require("../../constants.js");
const pda_js_1 = require("../../pda.js");
const transferQueue_js_1 = require("./transferQueue.js");
const crypto_js_1 = require("./crypto.js");
function getAssociatedTokenAddressSync(mint, owner, allowOwnerOffCurve = true, programId = constants_js_1.TOKEN_PROGRAM_ID, associatedTokenProgramId = constants_js_1.ASSOCIATED_TOKEN_PROGRAM_ID) {
    if (!allowOwnerOffCurve && !web3_js_1.PublicKey.isOnCurve(owner)) {
        throw new Error("Owner public key is off-curve");
    }
    const [ata] = web3_js_1.PublicKey.findProgramAddressSync([owner.toBuffer(), programId.toBuffer(), mint.toBuffer()], associatedTokenProgramId);
    return ata;
}
function createAssociatedTokenAccountIdempotentInstruction(payer, associatedToken, owner, mint, programId = constants_js_1.TOKEN_PROGRAM_ID, associatedTokenProgramId = constants_js_1.ASSOCIATED_TOKEN_PROGRAM_ID) {
    const data = Buffer.from([1]);
    return new web3_js_1.TransactionInstruction({
        programId: associatedTokenProgramId,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: associatedToken, isSigner: false, isWritable: true },
            { pubkey: owner, isSigner: false, isWritable: false },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
            { pubkey: programId, isSigner: false, isWritable: false },
        ],
        data,
    });
}
function createTransferInstruction(source, destination, owner, amount, multiSigners = [], programId = constants_js_1.TOKEN_PROGRAM_ID) {
    const data = Buffer.alloc(9);
    data[0] = 3;
    data.writeBigUInt64LE(amount, 1);
    const keys = [
        { pubkey: source, isSigner: false, isWritable: true },
        { pubkey: destination, isSigner: false, isWritable: true },
    ];
    if (multiSigners.length === 0) {
        keys.push({ pubkey: owner, isSigner: true, isWritable: false });
    }
    else {
        keys.push({ pubkey: owner, isSigner: false, isWritable: false });
        for (const signer of multiSigners) {
            keys.push({ pubkey: signer, isSigner: true, isWritable: false });
        }
    }
    return new web3_js_1.TransactionInstruction({
        programId,
        keys,
        data,
    });
}
function encodeLengthPrefixedBytes(bytes) {
    if (bytes.length > 0xff) {
        throw new Error("encrypted private transfer payload exceeds u8 length");
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
function u64leBuffer(value) {
    const out = Buffer.alloc(8);
    out.writeBigUInt64LE(value, 0);
    return out;
}
function decodeEphemeralAta(info) {
    if (info.data.length < 72) {
        throw new Error("Invalid EphemeralAta account data length");
    }
    const owner = new web3_js_1.PublicKey(info.data.subarray(0, 32));
    const mint = new web3_js_1.PublicKey(info.data.subarray(32, 64));
    const amount = BigInt(info.data.readBigUInt64LE(64));
    return {
        owner,
        mint,
        amount,
    };
}
function encodeEphemeralAta(eata) {
    const buffer = Buffer.alloc(72);
    buffer.set(eata.owner.toBytes(), 0);
    buffer.set(eata.mint.toBytes(), 32);
    buffer.writeBigUInt64LE(eata.amount, 64);
    return buffer;
}
function decodeGlobalVault(info) {
    if (info.data.length < 32) {
        throw new Error("Invalid GlobalVault account data length");
    }
    const mint = new web3_js_1.PublicKey(info.data.subarray(0, 32));
    return { mint };
}
function encodeGlobalVault(vault) {
    const buffer = Buffer.alloc(32);
    buffer.set(vault.mint.toBytes(), 0);
    return buffer;
}
function deriveEphemeralAta(owner, mint) {
    return web3_js_1.PublicKey.findProgramAddressSync([owner.toBuffer(), mint.toBuffer()], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
}
function deriveVault(mint) {
    return web3_js_1.PublicKey.findProgramAddressSync([mint.toBuffer()], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
}
function deriveRentPda() {
    return web3_js_1.PublicKey.findProgramAddressSync([Buffer.from("rent")], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
}
function deriveLamportsPda(payer, destination, salt) {
    if (salt.length !== 32) {
        throw new Error("salt must be exactly 32 bytes");
    }
    return web3_js_1.PublicKey.findProgramAddressSync([
        Buffer.from("lamports"),
        payer.toBuffer(),
        destination.toBuffer(),
        Buffer.from(salt),
    ], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
}
function deriveVaultAta(mint, vault) {
    return getAssociatedTokenAddressSync(mint, vault, true);
}
function deriveShuttleEphemeralAta(owner, mint, shuttleId) {
    if (!Number.isInteger(shuttleId) ||
        shuttleId < 0 ||
        shuttleId > 4294967295) {
        throw new Error("shuttleId must fit in u32");
    }
    const shuttleIdSeed = Buffer.alloc(4);
    shuttleIdSeed.writeUInt32LE(shuttleId, 0);
    return web3_js_1.PublicKey.findProgramAddressSync([owner.toBuffer(), mint.toBuffer(), shuttleIdSeed], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
}
function deriveShuttleAta(shuttleEphemeralAta, mint) {
    return web3_js_1.PublicKey.findProgramAddressSync([shuttleEphemeralAta.toBuffer(), mint.toBuffer()], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
}
function deriveShuttleWalletAta(mint, shuttleEphemeralAta) {
    return getAssociatedTokenAddressSync(mint, shuttleEphemeralAta, true);
}
function initEphemeralAtaIx(ephemeralAta, owner, mint, payer) {
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: ephemeralAta, isSigner: false, isWritable: true },
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: owner, isSigner: false, isWritable: false },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data: Buffer.from([0]),
    });
}
function initVaultAtaIx(payer, vaultAta, vault, mint) {
    return createAssociatedTokenAccountIdempotentInstruction(payer, vaultAta, vault, mint);
}
function initVaultIx(vault, mint, payer) {
    const [vaultEphemeralAta] = deriveEphemeralAta(vault, mint);
    const vaultAta = deriveVaultAta(mint, vault);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: vault, isSigner: false, isWritable: true },
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: vaultEphemeralAta, isSigner: false, isWritable: true },
            { pubkey: vaultAta, isSigner: false, isWritable: true },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
            {
                pubkey: constants_js_1.ASSOCIATED_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data: Buffer.from([1]),
    });
}
function initRentPdaIx(payer, rentPda) {
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: rentPda, isSigner: false, isWritable: true },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data: Buffer.from([23]),
    });
}
function transferToVaultIx(ephemeralAta, vault, mint, sourceAta, vaultAta, owner, amount) {
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: ephemeralAta, isSigner: false, isWritable: true },
            { pubkey: vault, isSigner: false, isWritable: false },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: sourceAta, isSigner: false, isWritable: true },
            { pubkey: vaultAta, isSigner: false, isWritable: true },
            { pubkey: owner, isSigner: true, isWritable: false },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        data: encodeAmountInstructionData(2, amount),
    });
}
function depositSplTokensIx(ephemeralAta, vault, mint, sourceAta, vaultAta, owner, amount) {
    return transferToVaultIx(ephemeralAta, vault, mint, sourceAta, vaultAta, owner, amount);
}
function delegateEphemeralAtaIx(payer, ephemeralAta, validator) {
    const data = validator
        ? Buffer.concat([Buffer.from([4]), validator.toBuffer()])
        : Buffer.from([4]);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: ephemeralAta, isSigner: false, isWritable: true },
            {
                pubkey: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            {
                pubkey: (0, pda_js_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(ephemeralAta, constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(ephemeralAta),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationMetadataPdaFromDelegatedAccount)(ephemeralAta),
                isSigner: false,
                isWritable: true,
            },
            { pubkey: constants_js_1.DELEGATION_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data,
    });
}
function initShuttleEphemeralAtaIx(payer, shuttleEphemeralAta, shuttleAta, shuttleWalletAta, owner, mint, shuttleId) {
    if (!Number.isInteger(shuttleId) ||
        shuttleId < 0 ||
        shuttleId > 4294967295) {
        throw new Error("shuttleId must fit in u32");
    }
    const data = Buffer.alloc(5);
    data[0] = 11;
    data.writeUInt32LE(shuttleId, 1);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: shuttleEphemeralAta, isSigner: false, isWritable: true },
            { pubkey: shuttleAta, isSigner: false, isWritable: true },
            { pubkey: shuttleWalletAta, isSigner: false, isWritable: true },
            { pubkey: owner, isSigner: false, isWritable: false },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
            {
                pubkey: constants_js_1.ASSOCIATED_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data,
    });
}
function delegateShuttleEphemeralAtaIx(payer, shuttleEphemeralAta, shuttleAta, validator) {
    const data = validator
        ? Buffer.concat([Buffer.from([13]), validator.toBuffer()])
        : Buffer.from([13]);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: shuttleEphemeralAta, isSigner: false, isWritable: false },
            { pubkey: shuttleAta, isSigner: false, isWritable: true },
            {
                pubkey: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            {
                pubkey: (0, pda_js_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(shuttleAta, constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(shuttleAta),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationMetadataPdaFromDelegatedAccount)(shuttleAta),
                isSigner: false,
                isWritable: true,
            },
            { pubkey: constants_js_1.DELEGATION_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data,
    });
}
function setupAndDelegateShuttleEphemeralAtaWithMergeIx(payer, shuttleEphemeralAta, shuttleAta, owner, sourceAta, destinationAta, shuttleWalletAta, mint, shuttleId, amount, validator) {
    if (!Number.isInteger(shuttleId) ||
        shuttleId < 0 ||
        shuttleId > 4294967295) {
        throw new Error("shuttleId must fit in u32");
    }
    const [rentPda] = deriveRentPda();
    const [vault] = deriveVault(mint);
    const vaultAta = deriveVaultAta(mint, vault);
    const data = validator ? Buffer.alloc(45) : Buffer.alloc(13);
    data[0] = 24;
    data.writeUInt32LE(shuttleId, 1);
    data.writeBigUInt64LE(amount, 5);
    if (validator) {
        validator.toBuffer().copy(data, 13);
    }
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: rentPda, isSigner: false, isWritable: true },
            { pubkey: shuttleEphemeralAta, isSigner: false, isWritable: true },
            { pubkey: shuttleAta, isSigner: false, isWritable: true },
            { pubkey: shuttleWalletAta, isSigner: false, isWritable: true },
            { pubkey: owner, isSigner: true, isWritable: false },
            {
                pubkey: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            {
                pubkey: (0, pda_js_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(shuttleAta, constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(shuttleAta),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationMetadataPdaFromDelegatedAccount)(shuttleAta),
                isSigner: false,
                isWritable: true,
            },
            { pubkey: constants_js_1.DELEGATION_PROGRAM_ID, isSigner: false, isWritable: false },
            {
                pubkey: constants_js_1.ASSOCIATED_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
            { pubkey: destinationAta, isSigner: false, isWritable: true },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: vault, isSigner: false, isWritable: false },
            { pubkey: sourceAta, isSigner: false, isWritable: true },
            { pubkey: vaultAta, isSigner: false, isWritable: true },
        ],
        data,
    });
}
function depositAndDelegateShuttleEphemeralAtaWithMergeAndPrivateTransferIx(payer, shuttleEphemeralAta, shuttleAta, owner, sourceAta, destinationOwner, shuttleWalletAta, mint, shuttleId, amount, minDelayMs, maxDelayMs, split, validator, clientRefId) {
    if (!Number.isInteger(shuttleId) ||
        shuttleId < 0 ||
        shuttleId > 4294967295) {
        throw new Error("shuttleId must fit in u32");
    }
    if (!Number.isInteger(split) || split <= 0 || split > 4294967295) {
        throw new Error("split must fit in u32");
    }
    if (amount < 0n ||
        minDelayMs < 0n ||
        maxDelayMs < 0n ||
        (clientRefId !== undefined && clientRefId < 0n)) {
        throw new Error("amount, delays, and clientRefId must be non-negative");
    }
    if (maxDelayMs < minDelayMs) {
        throw new Error("maxDelayMs must be greater than or equal to minDelayMs");
    }
    if (validator == null) {
        throw new Error("validator is required for encrypted private transfers");
    }
    const [rentPda] = deriveRentPda();
    const [vault] = deriveVault(mint);
    const vaultAta = deriveVaultAta(mint, vault);
    const [queue] = (0, transferQueue_js_1.deriveTransferQueue)(mint, validator);
    const encryptedDestination = (0, crypto_js_1.encryptEd25519Recipient)(destinationOwner.toBytes(), validator);
    const encryptedSuffix = (0, crypto_js_1.encryptEd25519Recipient)(packPrivateTransferSuffix(minDelayMs, maxDelayMs, split, clientRefId), validator);
    const data = Buffer.concat([
        Buffer.from([25]),
        u32leBuffer(shuttleId),
        u64leBuffer(amount),
        encodeLengthPrefixedBytes(validator.toBytes()),
        encodeLengthPrefixedBytes(encryptedDestination),
        encodeLengthPrefixedBytes(encryptedSuffix),
    ]);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: rentPda, isSigner: false, isWritable: true },
            { pubkey: shuttleEphemeralAta, isSigner: false, isWritable: true },
            { pubkey: shuttleAta, isSigner: false, isWritable: true },
            { pubkey: shuttleWalletAta, isSigner: false, isWritable: true },
            { pubkey: owner, isSigner: true, isWritable: false },
            {
                pubkey: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            {
                pubkey: (0, pda_js_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(shuttleAta, constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(shuttleAta),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationMetadataPdaFromDelegatedAccount)(shuttleAta),
                isSigner: false,
                isWritable: true,
            },
            { pubkey: constants_js_1.DELEGATION_PROGRAM_ID, isSigner: false, isWritable: false },
            {
                pubkey: constants_js_1.ASSOCIATED_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: vault, isSigner: false, isWritable: false },
            { pubkey: sourceAta, isSigner: false, isWritable: true },
            { pubkey: vaultAta, isSigner: false, isWritable: true },
            { pubkey: queue, isSigner: false, isWritable: true },
        ],
        data,
    });
}
function withdrawThroughDelegatedShuttleWithMergeIx(payer, shuttleEphemeralAta, shuttleAta, owner, ownerAta, shuttleWalletAta, mint, shuttleId, amount, validator) {
    if (!Number.isInteger(shuttleId) ||
        shuttleId < 0 ||
        shuttleId > 4294967295) {
        throw new Error("shuttleId must fit in u32");
    }
    if (amount < 0n) {
        throw new Error("amount must be non-negative");
    }
    const [rentPda] = deriveRentPda();
    const data = validator ? Buffer.alloc(45) : Buffer.alloc(13);
    data[0] = 26;
    data.writeUInt32LE(shuttleId, 1);
    data.writeBigUInt64LE(amount, 5);
    if (validator) {
        validator.toBuffer().copy(data, 13);
    }
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: rentPda, isSigner: false, isWritable: true },
            { pubkey: shuttleEphemeralAta, isSigner: false, isWritable: true },
            { pubkey: shuttleAta, isSigner: false, isWritable: true },
            { pubkey: shuttleWalletAta, isSigner: false, isWritable: true },
            { pubkey: owner, isSigner: true, isWritable: false },
            {
                pubkey: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            {
                pubkey: (0, pda_js_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(shuttleAta, constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(shuttleAta),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationMetadataPdaFromDelegatedAccount)(shuttleAta),
                isSigner: false,
                isWritable: true,
            },
            { pubkey: constants_js_1.DELEGATION_PROGRAM_ID, isSigner: false, isWritable: false },
            {
                pubkey: constants_js_1.ASSOCIATED_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
            { pubkey: ownerAta, isSigner: false, isWritable: true },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        data,
    });
}
function lamportsDelegatedTransferIx(payer, destination, amount, salt) {
    if (amount < 0n) {
        throw new Error("amount must be non-negative");
    }
    if (salt.length !== 32) {
        throw new Error("salt must be exactly 32 bytes");
    }
    const [rentPda] = deriveRentPda();
    const [lamportsPda] = deriveLamportsPda(payer, destination, salt);
    const destinationDelegationRecord = (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(destination);
    const data = Buffer.alloc(41);
    data[0] = 20;
    data.writeBigUInt64LE(amount, 1);
    Buffer.from(salt).copy(data, 9);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: rentPda, isSigner: false, isWritable: true },
            { pubkey: lamportsPda, isSigner: false, isWritable: true },
            {
                pubkey: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            {
                pubkey: (0, pda_js_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(lamportsPda, constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(lamportsPda),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationMetadataPdaFromDelegatedAccount)(lamportsPda),
                isSigner: false,
                isWritable: true,
            },
            { pubkey: constants_js_1.DELEGATION_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
            { pubkey: destination, isSigner: false, isWritable: true },
            {
                pubkey: destinationDelegationRecord,
                isSigner: false,
                isWritable: false,
            },
        ],
        data,
    });
}
function mergeShuttleIntoAtaIx(owner, destinationAta, shuttleEphemeralAta, shuttleWalletAta, mint) {
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: owner, isSigner: true, isWritable: false },
            { pubkey: destinationAta, isSigner: false, isWritable: true },
            { pubkey: shuttleEphemeralAta, isSigner: false, isWritable: false },
            { pubkey: shuttleWalletAta, isSigner: false, isWritable: true },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        data: Buffer.from([15]),
    });
}
function undelegateAndCloseShuttleEphemeralAtaIx(payer, rentReimbursement, shuttleEphemeralAta, shuttleAta, shuttleWalletAta, destinationAta, escrowIndex) {
    const data = escrowIndex === undefined
        ? Buffer.from([14])
        : Buffer.from([14, escrowIndex]);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: rentReimbursement, isSigner: false, isWritable: true },
            { pubkey: shuttleEphemeralAta, isSigner: false, isWritable: false },
            { pubkey: shuttleAta, isSigner: false, isWritable: false },
            { pubkey: shuttleWalletAta, isSigner: false, isWritable: true },
            { pubkey: destinationAta, isSigner: false, isWritable: true },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.MAGIC_CONTEXT_ID, isSigner: false, isWritable: true },
            { pubkey: constants_js_1.MAGIC_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        data,
    });
}
function withdrawSplIx(owner, mint, amount) {
    const [ephemeralAta] = deriveEphemeralAta(owner, mint);
    const [vault] = deriveVault(mint);
    const vaultAta = deriveVaultAta(mint, vault);
    const userDestAta = getAssociatedTokenAddressSync(mint, owner);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: owner, isSigner: true, isWritable: false },
            { pubkey: ephemeralAta, isSigner: false, isWritable: true },
            { pubkey: vault, isSigner: false, isWritable: false },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: vaultAta, isSigner: false, isWritable: true },
            { pubkey: userDestAta, isSigner: false, isWritable: true },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        data: encodeAmountInstructionData(3, amount),
    });
}
function undelegateIx(owner, mint) {
    const userAta = getAssociatedTokenAddressSync(mint, owner);
    const [ephemeralAta] = deriveEphemeralAta(owner, mint);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            {
                pubkey: owner,
                isSigner: true,
                isWritable: false,
            },
            {
                pubkey: userAta,
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: ephemeralAta,
                isSigner: false,
                isWritable: false,
            },
            {
                pubkey: constants_js_1.MAGIC_CONTEXT_ID,
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: constants_js_1.MAGIC_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
        ],
        data: Buffer.from([5]),
    });
}
function createEataPermissionIx(ephemeralAta, payer, flags = 0) {
    const permission = (0, pda_js_1.permissionPdaFromAccount)(ephemeralAta);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: ephemeralAta, isSigner: false, isWritable: true },
            { pubkey: permission, isSigner: false, isWritable: true },
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.PERMISSION_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        data: Buffer.from([6, flags]),
    });
}
function resetEataPermissionIx(ephemeralAta, payer, flags = 0) {
    const permission = (0, pda_js_1.permissionPdaFromAccount)(ephemeralAta);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: ephemeralAta, isSigner: false, isWritable: false },
            { pubkey: permission, isSigner: false, isWritable: true },
            { pubkey: payer, isSigner: true, isWritable: false },
            { pubkey: constants_js_1.PERMISSION_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        data: Buffer.from([9, flags]),
    });
}
function delegateEataPermissionIx(payer, ephemeralAta, validator) {
    const permission = (0, pda_js_1.permissionPdaFromAccount)(ephemeralAta);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: ephemeralAta, isSigner: false, isWritable: true },
            { pubkey: constants_js_1.PERMISSION_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: permission, isSigner: false, isWritable: true },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
            {
                pubkey: (0, pda_js_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(permission, constants_js_1.PERMISSION_PROGRAM_ID),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(permission),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationMetadataPdaFromDelegatedAccount)(permission),
                isSigner: false,
                isWritable: true,
            },
            { pubkey: constants_js_1.DELEGATION_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: validator, isSigner: false, isWritable: false },
        ],
        data: Buffer.from([7]),
    });
}
function undelegateEataPermissionIx(owner, ephemeralAta) {
    const permission = (0, pda_js_1.permissionPdaFromAccount)(ephemeralAta);
    return new web3_js_1.TransactionInstruction({
        programId: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
        keys: [
            { pubkey: owner, isSigner: true, isWritable: false },
            { pubkey: ephemeralAta, isSigner: false, isWritable: true },
            { pubkey: permission, isSigner: false, isWritable: true },
            { pubkey: constants_js_1.PERMISSION_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.MAGIC_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.MAGIC_CONTEXT_ID, isSigner: false, isWritable: true },
        ],
        data: Buffer.from([8]),
    });
}
function randomShuttleId() {
    const cryptoObj = globalThis?.crypto;
    if (cryptoObj?.getRandomValues !== undefined) {
        const buf = new Uint32Array(1);
        cryptoObj.getRandomValues(buf);
        return buf[0];
    }
    return Math.floor(Math.random() * 4294967296);
}
async function buildDelegateSplInstructions(owner, mint, amount, opts) {
    const payer = opts?.payer ?? owner;
    const validator = opts?.validator;
    const initIfMissing = opts?.initIfMissing ?? true;
    const initVaultIfMissing = opts?.initVaultIfMissing ?? initIfMissing;
    const isPrivate = opts?.private ?? false;
    const instructions = [];
    const [ephemeralAta] = deriveEphemeralAta(owner, mint);
    const [vault] = deriveVault(mint);
    const [vaultEphemeralAta] = deriveEphemeralAta(vault, mint);
    const vaultAta = deriveVaultAta(mint, vault);
    const ownerAta = getAssociatedTokenAddressSync(mint, owner);
    if (initIfMissing) {
        instructions.push(initEphemeralAtaIx(ephemeralAta, owner, mint, payer));
    }
    if (initVaultIfMissing) {
        instructions.push(initVaultIx(vault, mint, payer), initVaultAtaIx(payer, vaultAta, vault, mint), delegateEphemeralAtaIx(payer, vaultEphemeralAta, validator));
    }
    instructions.push(transferToVaultIx(ephemeralAta, vault, mint, ownerAta, vaultAta, owner, amount));
    if (isPrivate) {
        instructions.push(createEataPermissionIx(ephemeralAta, payer));
    }
    instructions.push(delegateEphemeralAtaIx(payer, ephemeralAta, validator));
    return instructions;
}
async function buildIdempotentDelegateSplInstructions(owner, mint, amount, opts) {
    const payer = opts?.payer ?? owner;
    const validator = opts?.validator;
    const initIfMissing = opts?.initIfMissing ?? true;
    const initVaultIfMissing = opts?.initVaultIfMissing ?? false;
    const initAtasIfMissing = opts?.initAtasIfMissing ?? false;
    const isPrivate = opts?.private ?? false;
    const shuttleId = opts?.shuttleId ?? randomShuttleId();
    const instructions = [];
    const [ephemeralAta] = deriveEphemeralAta(owner, mint);
    const [vault] = deriveVault(mint);
    const [vaultEphemeralAta] = deriveEphemeralAta(vault, mint);
    const vaultAta = deriveVaultAta(mint, vault);
    const ownerAta = getAssociatedTokenAddressSync(mint, owner);
    const [shuttleEphemeralAta] = deriveShuttleEphemeralAta(owner, mint, shuttleId);
    const [shuttleAta] = deriveShuttleAta(shuttleEphemeralAta, mint);
    const shuttleWalletAta = deriveShuttleWalletAta(mint, shuttleEphemeralAta);
    if (initVaultIfMissing) {
        instructions.push(initVaultIx(vault, mint, payer), initVaultAtaIx(payer, vaultAta, vault, mint), delegateEphemeralAtaIx(payer, vaultEphemeralAta, validator));
    }
    if (initAtasIfMissing) {
        instructions.push(createAssociatedTokenAccountIdempotentInstruction(payer, ownerAta, owner, mint));
    }
    if (initIfMissing) {
        instructions.push(initEphemeralAtaIx(ephemeralAta, owner, mint, payer));
    }
    if (isPrivate) {
        instructions.push(createEataPermissionIx(ephemeralAta, payer));
    }
    instructions.push(delegateEphemeralAtaIx(payer, ephemeralAta, validator));
    if (amount > 0n) {
        instructions.push(setupAndDelegateShuttleEphemeralAtaWithMergeIx(payer, shuttleEphemeralAta, shuttleAta, owner, ownerAta, ownerAta, shuttleWalletAta, mint, shuttleId, amount, validator));
    }
    else {
        instructions.push(initShuttleEphemeralAtaIx(payer, shuttleEphemeralAta, shuttleAta, shuttleWalletAta, owner, mint, shuttleId), delegateShuttleEphemeralAtaIx(payer, shuttleEphemeralAta, shuttleAta, validator));
    }
    return instructions;
}
async function delegateSpl(owner, mint, amount, opts) {
    if (opts?.idempotent === false) {
        return buildDelegateSplInstructions(owner, mint, amount, opts);
    }
    return buildIdempotentDelegateSplInstructions(owner, mint, amount, opts);
}
async function delegateSplWithPrivateTransfer(owner, mint, amount, opts) {
    const payer = opts?.payer ?? owner;
    const validator = opts?.validator;
    const initIfMissing = opts?.initIfMissing ?? true;
    const initVaultIfMissing = opts?.initVaultIfMissing ?? false;
    const initAtasIfMissing = opts?.initAtasIfMissing ?? false;
    const initTransferQueueIfMissing = opts?.initTransferQueueIfMissing ?? false;
    const shuttleId = opts?.shuttleId ?? randomShuttleId();
    const minDelayMs = opts?.minDelayMs ?? 0n;
    const maxDelayMs = opts?.maxDelayMs ?? minDelayMs;
    const split = opts?.split ?? 1;
    const clientRefId = opts?.clientRefId;
    if (validator == null) {
        throw new Error("validator is required for encrypted private transfers");
    }
    const instructions = [];
    const [ephemeralAta] = deriveEphemeralAta(owner, mint);
    const [vault] = deriveVault(mint);
    const [vaultEphemeralAta] = deriveEphemeralAta(vault, mint);
    const vaultAta = deriveVaultAta(mint, vault);
    const [queue] = (0, transferQueue_js_1.deriveTransferQueue)(mint, validator);
    const ownerAta = getAssociatedTokenAddressSync(mint, owner);
    const [shuttleEphemeralAta] = deriveShuttleEphemeralAta(owner, mint, shuttleId);
    const [shuttleAta] = deriveShuttleAta(shuttleEphemeralAta, mint);
    const shuttleWalletAta = deriveShuttleWalletAta(mint, shuttleEphemeralAta);
    if (initVaultIfMissing) {
        instructions.push(initVaultIx(vault, mint, payer), initVaultAtaIx(payer, vaultAta, vault, mint), delegateEphemeralAtaIx(payer, vaultEphemeralAta, validator));
    }
    if (initTransferQueueIfMissing) {
        instructions.push((0, transferQueue_js_1.toTransactionInstruction)((0, transferQueue_js_1.initTransferQueueIx)(payer, queue, mint, validator)));
    }
    if (initAtasIfMissing) {
        instructions.push(createAssociatedTokenAccountIdempotentInstruction(payer, ownerAta, owner, mint));
    }
    if (initIfMissing) {
        instructions.push(initEphemeralAtaIx(ephemeralAta, owner, mint, payer));
    }
    instructions.push(delegateEphemeralAtaIx(payer, ephemeralAta, validator), depositAndDelegateShuttleEphemeralAtaWithMergeAndPrivateTransferIx(payer, shuttleEphemeralAta, shuttleAta, owner, ownerAta, owner, shuttleWalletAta, mint, shuttleId, amount, minDelayMs, maxDelayMs, split, validator, clientRefId));
    return instructions;
}
async function transferSpl(from, to, mint, amount, opts) {
    const payer = opts.payer ?? from;
    const validator = opts.validator;
    const initIfMissing = opts.initIfMissing ?? false;
    const initAtasIfMissing = opts.initAtasIfMissing ?? false;
    const initVaultIfMissing = opts.initVaultIfMissing ?? false;
    const shuttleId = opts.shuttleId ?? randomShuttleId();
    const minDelayMs = opts.privateTransfer?.minDelayMs ?? 0n;
    const maxDelayMs = opts.privateTransfer?.maxDelayMs ?? minDelayMs;
    const split = opts.privateTransfer?.split ?? 1;
    const clientRefId = opts.privateTransfer?.clientRefId;
    const fromAta = getAssociatedTokenAddressSync(mint, from);
    const toAta = getAssociatedTokenAddressSync(mint, to);
    if (opts.fromBalance === "ephemeral") {
        switch (opts.visibility) {
            case "private":
                if (opts.toBalance === "base") {
                    if (validator == null) {
                        throw new Error("validator is required for private ephemeral-to-base transfers");
                    }
                    const [queue] = (0, transferQueue_js_1.deriveTransferQueue)(mint, validator);
                    const [vault] = deriveVault(mint);
                    const vaultAta = deriveVaultAta(mint, vault);
                    return [
                        (0, transferQueue_js_1.toTransactionInstruction)((0, transferQueue_js_1.depositAndQueueTransferIx)(queue, vault, mint, fromAta, vaultAta, to, from, amount, minDelayMs, maxDelayMs, split, undefined, clientRefId)),
                    ];
                }
                if (opts.toBalance === "ephemeral") {
                    return [createTransferInstruction(fromAta, toAta, from, amount)];
                }
                break;
            case "public":
                if (opts.toBalance === "ephemeral") {
                    return [createTransferInstruction(fromAta, toAta, from, amount)];
                }
                break;
        }
    }
    const instructions = [];
    if (initVaultIfMissing) {
        const [vault] = deriveVault(mint);
        const [vaultEphemeralAta] = deriveEphemeralAta(vault, mint);
        const vaultAta = deriveVaultAta(mint, vault);
        instructions.push(initVaultIx(vault, mint, payer), initVaultAtaIx(payer, vaultAta, vault, mint), delegateEphemeralAtaIx(payer, vaultEphemeralAta, validator));
    }
    if (opts.fromBalance === "base" && initAtasIfMissing) {
        instructions.push(createAssociatedTokenAccountIdempotentInstruction(payer, fromAta, from, mint));
    }
    const maybeRefillInstructions = () => {
        if (opts.fromBalance !== "base" || validator == null) {
            return [];
        }
        const [queue] = (0, transferQueue_js_1.deriveTransferQueue)(mint, validator);
        return [(0, transferQueue_js_1.processPendingTransferQueueRefillIx)(queue)];
    };
    switch (opts.visibility) {
        case "private":
            if (opts.fromBalance === "base" && opts.toBalance === "base") {
                const [shuttleEphemeralAta] = deriveShuttleEphemeralAta(from, mint, shuttleId);
                const [shuttleAta] = deriveShuttleAta(shuttleEphemeralAta, mint);
                const shuttleWalletAta = deriveShuttleWalletAta(mint, shuttleEphemeralAta);
                return [
                    ...instructions,
                    ...maybeRefillInstructions(),
                    depositAndDelegateShuttleEphemeralAtaWithMergeAndPrivateTransferIx(payer, shuttleEphemeralAta, shuttleAta, from, fromAta, to, shuttleWalletAta, mint, shuttleId, amount, minDelayMs, maxDelayMs, split, validator, clientRefId),
                ];
            }
            if (opts.fromBalance === "base" && opts.toBalance === "ephemeral") {
                if (initIfMissing) {
                    const [toEphemeralAta] = deriveEphemeralAta(to, mint);
                    instructions.push(createAssociatedTokenAccountIdempotentInstruction(payer, toAta, to, mint), initEphemeralAtaIx(toEphemeralAta, to, mint, payer), delegateEphemeralAtaIx(payer, toEphemeralAta, validator));
                }
                const [shuttleEphemeralAta] = deriveShuttleEphemeralAta(from, mint, shuttleId);
                const [shuttleAta] = deriveShuttleAta(shuttleEphemeralAta, mint);
                const shuttleWalletAta = deriveShuttleWalletAta(mint, shuttleEphemeralAta);
                return [
                    ...instructions,
                    setupAndDelegateShuttleEphemeralAtaWithMergeIx(payer, shuttleEphemeralAta, shuttleAta, from, fromAta, toAta, shuttleWalletAta, mint, shuttleId, amount, validator),
                ];
            }
            break;
        case "public":
            if (opts.fromBalance === "base" && opts.toBalance === "base") {
                return [
                    ...instructions,
                    createTransferInstruction(fromAta, toAta, from, amount),
                ];
            }
            break;
    }
    throw new Error(`transferSpl route not implemented: visibility=${opts.visibility}, fromBalance=${opts.fromBalance}, toBalance=${opts.toBalance}`);
}
async function buildIdempotentWithdrawSplInstructions(owner, mint, amount, opts) {
    const payer = opts?.payer ?? owner;
    const validator = opts?.validator;
    const initIfMissing = opts?.initIfMissing ?? true;
    const initAtasIfMissing = opts?.initAtasIfMissing ?? false;
    const shuttleId = opts?.shuttleId ?? randomShuttleId();
    const instructions = [];
    const [ephemeralAta] = deriveEphemeralAta(owner, mint);
    const ownerAta = getAssociatedTokenAddressSync(mint, owner);
    const [shuttleEphemeralAta] = deriveShuttleEphemeralAta(owner, mint, shuttleId);
    const [shuttleAta] = deriveShuttleAta(shuttleEphemeralAta, mint);
    const shuttleWalletAta = deriveShuttleWalletAta(mint, shuttleEphemeralAta);
    if (initAtasIfMissing) {
        instructions.push(createAssociatedTokenAccountIdempotentInstruction(payer, ownerAta, owner, mint));
    }
    if (initIfMissing) {
        instructions.push(initEphemeralAtaIx(ephemeralAta, owner, mint, payer));
    }
    instructions.push(delegateEphemeralAtaIx(payer, ephemeralAta, validator), withdrawThroughDelegatedShuttleWithMergeIx(payer, shuttleEphemeralAta, shuttleAta, owner, ownerAta, shuttleWalletAta, mint, shuttleId, amount, validator));
    return instructions;
}
async function withdrawSpl(owner, mint, amount, opts) {
    if (opts?.idempotent === false) {
        const instructions = [];
        if (opts?.initAtasIfMissing === true) {
            const payer = opts.payer ?? owner;
            const ownerAta = getAssociatedTokenAddressSync(mint, owner);
            instructions.push(createAssociatedTokenAccountIdempotentInstruction(payer, ownerAta, owner, mint));
        }
        instructions.push(withdrawSplIx(owner, mint, amount));
        return instructions;
    }
    return buildIdempotentWithdrawSplInstructions(owner, mint, amount, opts);
}
function encodeAmountInstructionData(discriminator, amount, ...suffix) {
    const data = Buffer.alloc(1 + 8 + suffix.length);
    data[0] = discriminator;
    data.writeBigUInt64LE(amount, 1);
    if (suffix.length > 0) {
        data.set(suffix, 9);
    }
    return data;
}
//# sourceMappingURL=ephemeralAta.js.map