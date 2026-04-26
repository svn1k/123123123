"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.toTransactionInstruction = toTransactionInstruction;
exports.deriveTransferQueue = deriveTransferQueue;
exports.initTransferQueueIx = initTransferQueueIx;
exports.allocateTransferQueueIx = allocateTransferQueueIx;
exports.depositAndQueueTransferIx = depositAndQueueTransferIx;
exports.ensureTransferQueueCrankIx = ensureTransferQueueCrankIx;
exports.delegateTransferQueueIx = delegateTransferQueueIx;
exports.processPendingTransferQueueRefillIx = processPendingTransferQueueRefillIx;
const web3_js_1 = require("@solana/web3.js");
const constants_js_1 = require("../../constants.js");
const pda_js_1 = require("../../pda.js");
const TRANSFER_QUEUE_SEED = Buffer.from("queue");
const QUEUE_REFILL_STATE_SEED = Buffer.from("queue-refill");
const RENT_PDA_SEED = Buffer.from("rent");
const LAMPORTS_PDA_SEED = Buffer.from("lamports");
const INITIALIZE_TRANSFER_QUEUE_DISCRIMINATOR = 12;
const DEPOSIT_AND_QUEUE_TRANSFER_DISCRIMINATOR = 16;
const ENSURE_TRANSFER_QUEUE_CRANK_DISCRIMINATOR = 17;
const DELEGATE_TRANSFER_QUEUE_DISCRIMINATOR = 19;
const ALLOCATE_TRANSFER_QUEUE_DISCRIMINATOR = 27;
const PROCESS_PENDING_TRANSFER_QUEUE_REFILL_DISCRIMINATOR = 28;
function toTransactionInstruction(instruction) {
    if ("keys" in instruction) {
        return instruction;
    }
    return new web3_js_1.TransactionInstruction({
        programId: instruction.programAddress,
        keys: instruction.accounts,
        data: Buffer.from(instruction.data),
    });
}
function deriveTransferQueue(mint, validator) {
    return web3_js_1.PublicKey.findProgramAddressSync([TRANSFER_QUEUE_SEED, mint.toBuffer(), validator.toBuffer()], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
}
function initTransferQueueIx(payer, queue, mint, validator, requestedItems) {
    return toTransactionInstruction({
        accounts: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: queue, isSigner: false, isWritable: true },
            {
                pubkey: (0, pda_js_1.permissionPdaFromAccount)(queue),
                isSigner: false,
                isWritable: true,
            },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: validator, isSigner: false, isWritable: false },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
            { pubkey: constants_js_1.PERMISSION_PROGRAM_ID, isSigner: false, isWritable: false },
        ],
        data: requestedItems === undefined
            ? new Uint8Array([INITIALIZE_TRANSFER_QUEUE_DISCRIMINATOR])
            : new Uint8Array([
                INITIALIZE_TRANSFER_QUEUE_DISCRIMINATOR,
                ...u32le(requestedItems),
            ]),
        programAddress: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
    });
}
function allocateTransferQueueIx(queue) {
    return toTransactionInstruction({
        accounts: [
            { pubkey: queue, isSigner: false, isWritable: true },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data: new Uint8Array([ALLOCATE_TRANSFER_QUEUE_DISCRIMINATOR]),
        programAddress: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
    });
}
function depositAndQueueTransferIx(queue, vault, mint, source, vaultAta, destination, owner, amount, minDelayMs = 0n, maxDelayMs = minDelayMs, split = 1, reimbursementTokenInfo = source, clientRefId) {
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
    const data = [
        DEPOSIT_AND_QUEUE_TRANSFER_DISCRIMINATOR,
        ...u64le(amount),
        ...u64le(minDelayMs),
        ...u64le(maxDelayMs),
        ...u32le(split),
    ];
    if (clientRefId !== undefined) {
        data.push(...u64le(clientRefId));
    }
    return toTransactionInstruction({
        accounts: [
            { pubkey: queue, isSigner: false, isWritable: true },
            { pubkey: vault, isSigner: false, isWritable: false },
            { pubkey: mint, isSigner: false, isWritable: false },
            { pubkey: source, isSigner: false, isWritable: true },
            { pubkey: vaultAta, isSigner: false, isWritable: true },
            { pubkey: destination, isSigner: false, isWritable: false },
            { pubkey: owner, isSigner: true, isWritable: false },
            { pubkey: constants_js_1.TOKEN_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: reimbursementTokenInfo, isSigner: false, isWritable: true },
        ],
        data: new Uint8Array(data),
        programAddress: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
    });
}
function ensureTransferQueueCrankIx(payer, queue, magicFeeVault, magicContext = constants_js_1.MAGIC_CONTEXT_ID, magicProgram = constants_js_1.MAGIC_PROGRAM_ID) {
    return toTransactionInstruction({
        accounts: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: queue, isSigner: false, isWritable: true },
            { pubkey: magicFeeVault, isSigner: false, isWritable: true },
            { pubkey: magicContext, isSigner: false, isWritable: true },
            { pubkey: magicProgram, isSigner: false, isWritable: false },
        ],
        data: new Uint8Array([ENSURE_TRANSFER_QUEUE_CRANK_DISCRIMINATOR]),
        programAddress: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
    });
}
function delegateTransferQueueIx(queue, payer, mint) {
    return toTransactionInstruction({
        accounts: [
            { pubkey: payer, isSigner: true, isWritable: true },
            { pubkey: queue, isSigner: false, isWritable: true },
            { pubkey: mint, isSigner: false, isWritable: false },
            {
                pubkey: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
                isSigner: false,
                isWritable: false,
            },
            {
                pubkey: (0, pda_js_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(queue, constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(queue),
                isSigner: false,
                isWritable: true,
            },
            {
                pubkey: (0, pda_js_1.delegationMetadataPdaFromDelegatedAccount)(queue),
                isSigner: false,
                isWritable: true,
            },
            { pubkey: constants_js_1.DELEGATION_PROGRAM_ID, isSigner: false, isWritable: false },
            { pubkey: web3_js_1.SystemProgram.programId, isSigner: false, isWritable: false },
        ],
        data: new Uint8Array([DELEGATE_TRANSFER_QUEUE_DISCRIMINATOR]),
        programAddress: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
    });
}
function processPendingTransferQueueRefillIx(queue) {
    const [rentPda] = web3_js_1.PublicKey.findProgramAddressSync([RENT_PDA_SEED], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
    const [refillState] = web3_js_1.PublicKey.findProgramAddressSync([QUEUE_REFILL_STATE_SEED, queue.toBuffer()], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
    const [lamportsPda] = web3_js_1.PublicKey.findProgramAddressSync([LAMPORTS_PDA_SEED, rentPda.toBuffer(), queue.toBuffer(), queue.toBuffer()], constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
    return toTransactionInstruction({
        accounts: [
            { pubkey: refillState, isSigner: false, isWritable: true },
            { pubkey: queue, isSigner: false, isWritable: true },
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
            {
                pubkey: (0, pda_js_1.delegationRecordPdaFromDelegatedAccount)(queue),
                isSigner: false,
                isWritable: false,
            },
        ],
        data: new Uint8Array([PROCESS_PENDING_TRANSFER_QUEUE_REFILL_DISCRIMINATOR]),
        programAddress: constants_js_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID,
    });
}
function u32le(n) {
    if (!Number.isInteger(n) || n < 0 || n > 4294967295) {
        throw new Error("value out of range for u32");
    }
    return [n & 0xff, (n >>> 8) & 0xff, (n >>> 16) & 0xff, (n >>> 24) & 0xff];
}
function u64le(n) {
    if (n < 0n || n > 0xffffffffffffffffn) {
        throw new Error("value out of range for u64");
    }
    const out = Buffer.alloc(8);
    out.writeBigUInt64LE(n);
    return Array.from(out);
}
//# sourceMappingURL=transferQueue.js.map