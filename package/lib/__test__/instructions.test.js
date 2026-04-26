"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const vitest_1 = require("vitest");
const web3_js_1 = require("@solana/web3.js");
const delegation_program_1 = require("../instructions/delegation-program");
const magic_program_1 = require("../instructions/magic-program");
const ephemeral_spl_token_program_1 = require("../instructions/ephemeral-spl-token-program");
const constants_1 = require("../constants");
const pda_1 = require("../pda");
function readLengthPrefixedField(data, offset) {
    const len = data[offset];
    const start = offset + 1;
    const end = start + len;
    return [Buffer.from(data.subarray(start, end)), end];
}
(0, vitest_1.describe)("Exposed Instructions (web3.js)", () => {
    const mockPublicKey = new web3_js_1.PublicKey("11111111111111111111111111111111");
    const differentKey = new web3_js_1.PublicKey("11111111111111111111111111111112");
    (0, vitest_1.describe)("delegate instruction", () => {
        (0, vitest_1.it)("should create a delegate instruction with correct parameters", () => {
            const args = {
                commitFrequencyMs: 1000,
                seeds: [],
            };
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            }, args);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(7);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThan(0);
            (0, vitest_1.expect)(instruction.programId.toBase58()).toBe(constants_1.DELEGATION_PROGRAM_ID.toBase58());
        });
        (0, vitest_1.it)("should create a delegate instruction without validator", () => {
            const args = {
                commitFrequencyMs: 1000,
                seeds: [],
            };
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            }, args);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(7);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThan(0);
        });
        (0, vitest_1.it)("should include all required account keys", () => {
            const args = {
                commitFrequencyMs: 1000,
                seeds: [],
            };
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            }, args);
            const keyCount = instruction.keys.length;
            (0, vitest_1.expect)(keyCount).toBe(7);
            instruction.keys.forEach((key) => {
                (0, vitest_1.expect)(key.pubkey).toBeDefined();
                (0, vitest_1.expect)(key.isSigner).toBeDefined();
                (0, vitest_1.expect)(key.isWritable).toBeDefined();
            });
        });
        (0, vitest_1.it)("should serialize validator in args when provided in accounts", () => {
            const args = {
                commitFrequencyMs: 1000,
                seeds: [],
            };
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
                validator: mockPublicKey,
            }, args);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(7);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThanOrEqual(8 + 4 + 4 + 1 + 32);
        });
        (0, vitest_1.it)("should allow validator override via args", () => {
            const validatorFromArgs = new web3_js_1.PublicKey("11111111111111111111111111111112");
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
                validator: mockPublicKey,
            }, {
                commitFrequencyMs: 1000,
                seeds: [],
                validator: validatorFromArgs,
            });
            (0, vitest_1.expect)(instruction.keys).toHaveLength(7);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
        });
        (0, vitest_1.it)("should support different account addresses", () => {
            const args = {
                commitFrequencyMs: 1000,
                seeds: [],
            };
            const instruction1 = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            }, args);
            const instruction2 = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: differentKey,
                ownerProgram: mockPublicKey,
            }, args);
            (0, vitest_1.expect)(instruction1.data).toBeDefined();
            (0, vitest_1.expect)(instruction2.data).toBeDefined();
        });
        (0, vitest_1.it)("should handle various commitFrequencyMs values", () => {
            const frequencies = [0, 1000, 5000, 60000];
            frequencies.forEach((freq) => {
                const args = {
                    commitFrequencyMs: freq,
                    seeds: [],
                };
                const instruction = (0, delegation_program_1.createDelegateInstruction)({
                    payer: mockPublicKey,
                    delegatedAccount: mockPublicKey,
                    ownerProgram: mockPublicKey,
                }, args);
                (0, vitest_1.expect)(instruction.data).toBeDefined();
            });
        });
        (0, vitest_1.it)("should use default commitFrequencyMs when args not provided", () => {
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            });
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.keys).toHaveLength(7);
            (0, vitest_1.expect)(instruction.programId.toBase58()).toBe(constants_1.DELEGATION_PROGRAM_ID.toBase58());
        });
        (0, vitest_1.it)("should handle multiple seeds", () => {
            const args = {
                commitFrequencyMs: 1000,
                seeds: [new Uint8Array([1, 2, 3]), new Uint8Array([4, 5, 6])],
            };
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            }, args);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
        });
        (0, vitest_1.it)("should serialize commitFrequencyMs as u32", () => {
            const args = {
                commitFrequencyMs: 1000,
                seeds: [],
            };
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            }, args);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            const minSize = 8 + 4 + 4;
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThanOrEqual(minSize);
            (0, vitest_1.expect)(instruction.data.readUInt32LE(8)).toBe(1000);
        });
        (0, vitest_1.it)("should serialize with default commitFrequencyMs as max u32", () => {
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            });
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.readUInt32LE(8)).toBe(0xffffffff);
        });
        (0, vitest_1.it)("should serialize seeds array correctly", () => {
            const args = {
                commitFrequencyMs: 1000,
                seeds: [new Uint8Array([1, 2, 3]), new Uint8Array([4, 5, 6])],
            };
            const instruction = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            }, args);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.readUInt32LE(12)).toBe(2);
        });
    });
    (0, vitest_1.describe)("initRentPdaIx (Ephemeral SPL Token Program)", () => {
        (0, vitest_1.it)("should derive and initialize the global rent PDA", () => {
            const [rentPda] = (0, ephemeral_spl_token_program_1.deriveRentPda)();
            const instruction = (0, ephemeral_spl_token_program_1.initRentPdaIx)(mockPublicKey, rentPda);
            (0, vitest_1.expect)(instruction.programId.toBase58()).toBe(constants_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID.toBase58());
            (0, vitest_1.expect)(instruction.keys).toHaveLength(3);
            (0, vitest_1.expect)(instruction.keys[0].pubkey.toBase58()).toBe(mockPublicKey.toBase58());
            (0, vitest_1.expect)(instruction.keys[0].isSigner).toBe(true);
            (0, vitest_1.expect)(instruction.keys[1].pubkey.toBase58()).toBe(rentPda.toBase58());
            (0, vitest_1.expect)(instruction.data).toEqual(Buffer.from([23]));
        });
    });
    (0, vitest_1.describe)("topUpEscrow instruction", () => {
        (0, vitest_1.it)("should create a topUpEscrow instruction with all parameters", () => {
            const instruction = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, 1000000, 255);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(4);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBe(17);
            (0, vitest_1.expect)(instruction.programId.toBase58()).toBe(constants_1.DELEGATION_PROGRAM_ID.toBase58());
        });
        (0, vitest_1.it)("should create a topUpEscrow instruction with default index", () => {
            const instruction = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, 1000000);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(4);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBe(17);
            (0, vitest_1.expect)(instruction.data[0]).toBe(9);
            for (let i = 1; i < 8; i++) {
                (0, vitest_1.expect)(instruction.data[i]).toBe(0);
            }
            const amount = instruction.data.readBigUInt64LE(8);
            (0, vitest_1.expect)(amount).toBe(BigInt(1000000));
            (0, vitest_1.expect)(instruction.data[16]).toBe(255);
        });
        (0, vitest_1.it)("should convert number amount to bigint internally", () => {
            const instruction = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, 1234567);
            const amount = instruction.data.readBigUInt64LE(8);
            (0, vitest_1.expect)(amount).toBe(BigInt(1234567));
        });
        (0, vitest_1.it)("should handle custom index values", () => {
            const testIndices = [0, 1, 100, 254, 255];
            testIndices.forEach((index) => {
                const instruction = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, 1000000, index);
                (0, vitest_1.expect)(instruction.data[16]).toBe(index);
            });
        });
        (0, vitest_1.it)("should handle zero amount", () => {
            const instruction = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, 0);
            const amount = instruction.data.readBigUInt64LE(8);
            (0, vitest_1.expect)(amount).toBe(BigInt(0));
        });
        (0, vitest_1.it)("should handle large amounts", () => {
            const largeAmount = 9007199254740991;
            const instruction = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, largeAmount);
            const amount = instruction.data.readBigUInt64LE(8);
            (0, vitest_1.expect)(amount).toBe(BigInt(largeAmount));
        });
        (0, vitest_1.it)("should include correct account keys", () => {
            const instruction = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, 1000000);
            (0, vitest_1.expect)(instruction.keys.length).toBe(4);
            instruction.keys.forEach((key) => {
                (0, vitest_1.expect)(key.pubkey).toBeDefined();
                (0, vitest_1.expect)(typeof key.isSigner).toBe("boolean");
                (0, vitest_1.expect)(typeof key.isWritable).toBe("boolean");
            });
        });
        (0, vitest_1.it)("should use consistent data format for the same params", () => {
            const instruction1 = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, 1000000);
            const instruction2 = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, 1000000);
            (0, vitest_1.expect)(instruction1.data).toEqual(instruction2.data);
        });
    });
    (0, vitest_1.describe)("closeEscrow instruction", () => {
        (0, vitest_1.it)("should create a closeEscrow instruction with all parameters", () => {
            const instruction = (0, delegation_program_1.createCloseEscrowInstruction)(mockPublicKey, mockPublicKey, 255);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(3);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBe(9);
            (0, vitest_1.expect)(instruction.programId.toBase58()).toBe(constants_1.DELEGATION_PROGRAM_ID.toBase58());
        });
        (0, vitest_1.it)("should create a closeEscrow instruction with default index", () => {
            const instruction = (0, delegation_program_1.createCloseEscrowInstruction)(mockPublicKey, mockPublicKey);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(3);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBe(9);
            (0, vitest_1.expect)(instruction.data[0]).toBe(11);
            for (let i = 1; i < 8; i++) {
                (0, vitest_1.expect)(instruction.data[i]).toBe(0);
            }
            (0, vitest_1.expect)(instruction.data[8]).toBe(255);
        });
        (0, vitest_1.it)("should handle custom index values", () => {
            const testIndices = [0, 1, 100, 254, 255];
            testIndices.forEach((index) => {
                const instruction = (0, delegation_program_1.createCloseEscrowInstruction)(mockPublicKey, mockPublicKey, index);
                (0, vitest_1.expect)(instruction.data[8]).toBe(index);
            });
        });
        (0, vitest_1.it)("should include correct account keys", () => {
            const instruction = (0, delegation_program_1.createCloseEscrowInstruction)(mockPublicKey, mockPublicKey);
            (0, vitest_1.expect)(instruction.keys.length).toBe(3);
            instruction.keys.forEach((key) => {
                (0, vitest_1.expect)(key.pubkey).toBeDefined();
                (0, vitest_1.expect)(typeof key.isSigner).toBe("boolean");
                (0, vitest_1.expect)(typeof key.isWritable).toBe("boolean");
            });
        });
        (0, vitest_1.it)("should use consistent data format for the same params", () => {
            const instruction1 = (0, delegation_program_1.createCloseEscrowInstruction)(mockPublicKey, mockPublicKey);
            const instruction2 = (0, delegation_program_1.createCloseEscrowInstruction)(mockPublicKey, mockPublicKey);
            (0, vitest_1.expect)(instruction1.data).toEqual(instruction2.data);
        });
        (0, vitest_1.it)("should have correct discriminator", () => {
            const instruction = (0, delegation_program_1.createCloseEscrowInstruction)(mockPublicKey, mockPublicKey);
            (0, vitest_1.expect)(instruction.data[0]).toBe(11);
        });
    });
    (0, vitest_1.describe)("Cross-instruction consistency", () => {
        (0, vitest_1.it)("should all target the same delegation program", () => {
            const delegateArgs = {
                commitFrequencyMs: 1000,
                seeds: [],
            };
            const delegateInstr = (0, delegation_program_1.createDelegateInstruction)({
                payer: mockPublicKey,
                delegatedAccount: mockPublicKey,
                ownerProgram: mockPublicKey,
            }, delegateArgs);
            const topUpInstr = (0, delegation_program_1.createTopUpEscrowInstruction)(mockPublicKey, mockPublicKey, mockPublicKey, 1000000);
            const closeInstr = (0, delegation_program_1.createCloseEscrowInstruction)(mockPublicKey, mockPublicKey);
            const programId = constants_1.DELEGATION_PROGRAM_ID.toBase58();
            (0, vitest_1.expect)(delegateInstr.programId.toBase58()).toBe(programId);
            (0, vitest_1.expect)(topUpInstr.programId.toBase58()).toBe(programId);
            (0, vitest_1.expect)(closeInstr.programId.toBase58()).toBe(programId);
        });
    });
    (0, vitest_1.describe)("scheduleCommit instruction (Magic Program)", () => {
        (0, vitest_1.it)("should create a scheduleCommit instruction with required parameters", () => {
            const instruction = (0, magic_program_1.createCommitInstruction)(mockPublicKey, [
                mockPublicKey,
            ]);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(3);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBe(4);
            (0, vitest_1.expect)(instruction.programId.toBase58()).toBe(constants_1.MAGIC_PROGRAM_ID.toBase58());
        });
        (0, vitest_1.it)("should have correct discriminator", () => {
            const instruction = (0, magic_program_1.createCommitInstruction)(mockPublicKey, [
                mockPublicKey,
            ]);
            (0, vitest_1.expect)(instruction.data.readUInt32LE(0)).toBe(1);
        });
        (0, vitest_1.it)("should include payer as signer and writable", () => {
            const instruction = (0, magic_program_1.createCommitInstruction)(mockPublicKey, [
                mockPublicKey,
            ]);
            (0, vitest_1.expect)(instruction.keys[0].pubkey.toBase58()).toBe(mockPublicKey.toBase58());
            (0, vitest_1.expect)(instruction.keys[0].isSigner).toBe(true);
            (0, vitest_1.expect)(instruction.keys[0].isWritable).toBe(true);
        });
        (0, vitest_1.it)("should include magic context as writable", () => {
            const instruction = (0, magic_program_1.createCommitInstruction)(mockPublicKey, [
                mockPublicKey,
            ]);
            (0, vitest_1.expect)(instruction.keys[1].pubkey.toBase58()).toBe(constants_1.MAGIC_CONTEXT_ID.toBase58());
            (0, vitest_1.expect)(instruction.keys[1].isSigner).toBe(false);
            (0, vitest_1.expect)(instruction.keys[1].isWritable).toBe(true);
        });
        (0, vitest_1.it)("should include accounts to commit as readonly", () => {
            const accountsToCommit = [
                new web3_js_1.PublicKey("11111111111111111111111111111113"),
                new web3_js_1.PublicKey("11111111111111111111111111111114"),
            ];
            const instruction = (0, magic_program_1.createCommitInstruction)(mockPublicKey, accountsToCommit);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(4);
            (0, vitest_1.expect)(instruction.keys[2].pubkey.toBase58()).toBe(accountsToCommit[0].toBase58());
            (0, vitest_1.expect)(instruction.keys[2].isSigner).toBe(false);
            (0, vitest_1.expect)(instruction.keys[2].isWritable).toBe(false);
            (0, vitest_1.expect)(instruction.keys[3].pubkey.toBase58()).toBe(accountsToCommit[1].toBase58());
        });
        (0, vitest_1.it)("should handle single account to commit", () => {
            const instruction = (0, magic_program_1.createCommitInstruction)(mockPublicKey, [
                differentKey,
            ]);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(3);
            (0, vitest_1.expect)(instruction.keys[2].pubkey.toBase58()).toBe(differentKey.toBase58());
        });
        (0, vitest_1.it)("should handle multiple accounts to commit", () => {
            const accounts = [
                new web3_js_1.PublicKey("11111111111111111111111111111113"),
                new web3_js_1.PublicKey("11111111111111111111111111111114"),
                new web3_js_1.PublicKey("11111111111111111111111111111115"),
            ];
            const instruction = (0, magic_program_1.createCommitInstruction)(mockPublicKey, accounts);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(5);
            accounts.forEach((account, index) => {
                (0, vitest_1.expect)(instruction.keys[2 + index].pubkey.toBase58()).toBe(account.toBase58());
            });
        });
    });
    (0, vitest_1.describe)("scheduleCommitAndUndelegate instruction (Magic Program)", () => {
        (0, vitest_1.it)("should create a scheduleCommitAndUndelegate instruction with required parameters", () => {
            const instruction = (0, magic_program_1.createCommitAndUndelegateInstruction)(mockPublicKey, [
                mockPublicKey,
            ]);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(3);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBe(4);
            (0, vitest_1.expect)(instruction.programId.toBase58()).toBe(constants_1.MAGIC_PROGRAM_ID.toBase58());
        });
        (0, vitest_1.it)("should have correct discriminator", () => {
            const instruction = (0, magic_program_1.createCommitAndUndelegateInstruction)(mockPublicKey, [
                mockPublicKey,
            ]);
            (0, vitest_1.expect)(instruction.data.readUInt32LE(0)).toBe(2);
        });
        (0, vitest_1.it)("should include payer as signer and writable", () => {
            const instruction = (0, magic_program_1.createCommitAndUndelegateInstruction)(mockPublicKey, [
                mockPublicKey,
            ]);
            (0, vitest_1.expect)(instruction.keys[0].pubkey.toBase58()).toBe(mockPublicKey.toBase58());
            (0, vitest_1.expect)(instruction.keys[0].isSigner).toBe(true);
            (0, vitest_1.expect)(instruction.keys[0].isWritable).toBe(true);
        });
        (0, vitest_1.it)("should include magic context as writable", () => {
            const instruction = (0, magic_program_1.createCommitAndUndelegateInstruction)(mockPublicKey, [
                mockPublicKey,
            ]);
            (0, vitest_1.expect)(instruction.keys[1].pubkey.toBase58()).toBe(constants_1.MAGIC_CONTEXT_ID.toBase58());
            (0, vitest_1.expect)(instruction.keys[1].isSigner).toBe(false);
            (0, vitest_1.expect)(instruction.keys[1].isWritable).toBe(true);
        });
        (0, vitest_1.it)("should include accounts to commit and undelegate as writable", () => {
            const accountsToCommitAndUndelegate = [
                new web3_js_1.PublicKey("11111111111111111111111111111113"),
                new web3_js_1.PublicKey("11111111111111111111111111111114"),
            ];
            const instruction = (0, magic_program_1.createCommitAndUndelegateInstruction)(mockPublicKey, accountsToCommitAndUndelegate);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(4);
            (0, vitest_1.expect)(instruction.keys[2].pubkey.toBase58()).toBe(accountsToCommitAndUndelegate[0].toBase58());
            (0, vitest_1.expect)(instruction.keys[2].isSigner).toBe(false);
            (0, vitest_1.expect)(instruction.keys[2].isWritable).toBe(true);
            (0, vitest_1.expect)(instruction.keys[3].pubkey.toBase58()).toBe(accountsToCommitAndUndelegate[1].toBase58());
            (0, vitest_1.expect)(instruction.keys[3].isWritable).toBe(true);
        });
        (0, vitest_1.it)("should mark every delegated PDA writable across multiple accounts", () => {
            const delegatedAccounts = [
                new web3_js_1.PublicKey("11111111111111111111111111111113"),
                new web3_js_1.PublicKey("11111111111111111111111111111114"),
                new web3_js_1.PublicKey("11111111111111111111111111111115"),
            ];
            const instruction = (0, magic_program_1.createCommitAndUndelegateInstruction)(mockPublicKey, delegatedAccounts);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(5);
            delegatedAccounts.forEach((_, index) => {
                (0, vitest_1.expect)(instruction.keys[2 + index].isWritable).toBe(true);
            });
        });
        (0, vitest_1.it)("should handle single account to commit and undelegate", () => {
            const instruction = (0, magic_program_1.createCommitAndUndelegateInstruction)(mockPublicKey, [
                differentKey,
            ]);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(3);
            (0, vitest_1.expect)(instruction.keys[2].pubkey.toBase58()).toBe(differentKey.toBase58());
        });
        (0, vitest_1.it)("should handle multiple accounts to commit and undelegate", () => {
            const accounts = [
                new web3_js_1.PublicKey("11111111111111111111111111111113"),
                new web3_js_1.PublicKey("11111111111111111111111111111114"),
                new web3_js_1.PublicKey("11111111111111111111111111111115"),
            ];
            const instruction = (0, magic_program_1.createCommitAndUndelegateInstruction)(mockPublicKey, accounts);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(5);
            accounts.forEach((account, index) => {
                (0, vitest_1.expect)(instruction.keys[2 + index].pubkey.toBase58()).toBe(account.toBase58());
            });
        });
    });
    (0, vitest_1.describe)("delegateSpl (Ephemeral SPL Token Program)", () => {
        const owner = new web3_js_1.PublicKey("11111111111111111111111111111113");
        const mint = new web3_js_1.PublicKey("11111111111111111111111111111114");
        const validator = new web3_js_1.PublicKey("11111111111111111111111111111115");
        (0, vitest_1.it)("should delegate the vault eata when initializing the vault in legacy flow", async () => {
            const [vault] = (0, ephemeral_spl_token_program_1.deriveVault)(mint);
            const [vaultEphemeralAta] = (0, ephemeral_spl_token_program_1.deriveEphemeralAta)(vault, mint);
            const instructions = await (0, ephemeral_spl_token_program_1.delegateSpl)(owner, mint, 1n, {
                validator,
                initIfMissing: true,
                initVaultIfMissing: true,
                idempotent: false,
            });
            (0, vitest_1.expect)(instructions[3].keys[1].pubkey.toBase58()).toBe(vaultEphemeralAta.toBase58());
            (0, vitest_1.expect)(instructions[3].data[0]).toBe(4);
            (0, vitest_1.expect)(Buffer.from(instructions[3].data.subarray(1)).equals(validator.toBuffer())).toBe(true);
        });
        (0, vitest_1.it)("should delegate the vault eata when initializing the vault in idempotent flow", async () => {
            const [vault] = (0, ephemeral_spl_token_program_1.deriveVault)(mint);
            const [vaultEphemeralAta] = (0, ephemeral_spl_token_program_1.deriveEphemeralAta)(vault, mint);
            const instructions = await (0, ephemeral_spl_token_program_1.delegateSpl)(owner, mint, 1n, {
                validator,
                initVaultIfMissing: true,
                shuttleId: 7,
            });
            (0, vitest_1.expect)(instructions[2].keys[1].pubkey.toBase58()).toBe(vaultEphemeralAta.toBase58());
            (0, vitest_1.expect)(instructions[2].data[0]).toBe(4);
            (0, vitest_1.expect)(Buffer.from(instructions[2].data.subarray(1)).equals(validator.toBuffer())).toBe(true);
        });
        (0, vitest_1.it)("should use setup_and_delegate_shuttle_with_merge in idempotent flow when amount is nonzero", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.delegateSpl)(owner, mint, 1n, {
                validator,
                shuttleId: 7,
            });
            const setupAndDelegateInstruction = instructions.find((ix) => ix.data[0] === 24);
            (0, vitest_1.expect)(setupAndDelegateInstruction).toBeDefined();
            if (setupAndDelegateInstruction == null) {
                throw new Error("Expected setup_and_delegate instruction");
            }
            (0, vitest_1.expect)(setupAndDelegateInstruction?.keys).toHaveLength(19);
            (0, vitest_1.expect)(instructions.find((ix) => ix.data[0] === 11)).toBeUndefined();
            (0, vitest_1.expect)(Buffer.from(setupAndDelegateInstruction.data).readBigUInt64LE(5)).toBe(1n);
            (0, vitest_1.expect)(Buffer.from(setupAndDelegateInstruction.data.subarray(13)).equals(validator.toBuffer())).toBe(true);
        });
        (0, vitest_1.it)("should keep the shuttle eata writable in the zero-amount shuttle setup flow", async () => {
            const [shuttleEphemeralAta] = (0, ephemeral_spl_token_program_1.deriveShuttleEphemeralAta)(owner, mint, 7);
            const [shuttleAta] = (0, ephemeral_spl_token_program_1.deriveShuttleAta)(shuttleEphemeralAta, mint);
            const instructions = await (0, ephemeral_spl_token_program_1.delegateSpl)(owner, mint, 0n, {
                validator,
                shuttleId: 7,
            });
            const initShuttleInstruction = instructions.find((ix) => ix.data[0] === 11);
            const delegateShuttleInstruction = instructions.find((ix) => ix.data[0] === 13);
            (0, vitest_1.expect)(initShuttleInstruction).toBeDefined();
            (0, vitest_1.expect)(delegateShuttleInstruction).toBeDefined();
            (0, vitest_1.expect)(initShuttleInstruction?.keys[2].pubkey.toBase58()).toBe(shuttleAta.toBase58());
            (0, vitest_1.expect)(delegateShuttleInstruction?.keys[2].pubkey.toBase58()).toBe(shuttleAta.toBase58());
            (0, vitest_1.expect)(initShuttleInstruction?.keys[2].isWritable).toBe(true);
            (0, vitest_1.expect)(delegateShuttleInstruction?.keys[2].isWritable).toBe(true);
        });
    });
    (0, vitest_1.describe)("delegateSplWithPrivateTransfer (Ephemeral SPL Token Program)", () => {
        const owner = new web3_js_1.PublicKey("11111111111111111111111111111113");
        const mint = new web3_js_1.PublicKey("11111111111111111111111111111114");
        const validator = web3_js_1.Keypair.generate().publicKey;
        (0, vitest_1.it)("should use the private transfer shuttle flow", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.delegateSplWithPrivateTransfer)(owner, mint, 1n, {
                validator,
                shuttleId: 7,
                initTransferQueueIfMissing: true,
                minDelayMs: 100n,
                maxDelayMs: 300n,
                split: 4,
            });
            const privateTransferInstruction = instructions.find((ix) => ix.data[0] === 25);
            (0, vitest_1.expect)(instructions.find((ix) => ix.data[0] === 12)).toBeDefined();
            (0, vitest_1.expect)(privateTransferInstruction).toBeDefined();
            if (privateTransferInstruction == null) {
                throw new Error("Expected private transfer instruction");
            }
            (0, vitest_1.expect)(privateTransferInstruction?.keys).toHaveLength(19);
            const data = Buffer.from(privateTransferInstruction.data);
            (0, vitest_1.expect)(data.readUInt32LE(1)).toBe(7);
            (0, vitest_1.expect)(data.readBigUInt64LE(5)).toBe(1n);
            const [validatorField, nextOffset] = readLengthPrefixedField(data, 13);
            const [destinationField, suffixOffset] = readLengthPrefixedField(data, nextOffset);
            const [suffixField, endOffset] = readLengthPrefixedField(data, suffixOffset);
            (0, vitest_1.expect)(validatorField.equals(validator.toBuffer())).toBe(true);
            (0, vitest_1.expect)(destinationField).toHaveLength(80);
            (0, vitest_1.expect)(suffixField).toHaveLength(68);
            (0, vitest_1.expect)(endOffset).toBe(data.length);
        });
    });
    (0, vitest_1.describe)("withdrawSpl (Ephemeral SPL Token Program)", () => {
        const owner = new web3_js_1.PublicKey("11111111111111111111111111111113");
        const mint = new web3_js_1.PublicKey("11111111111111111111111111111114");
        const validator = new web3_js_1.PublicKey("11111111111111111111111111111115");
        (0, vitest_1.it)("should use the delegated shuttle withdrawal flow when idempotent", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.withdrawSpl)(owner, mint, 1n, {
                validator,
                shuttleId: 7,
            });
            const withdrawInstruction = instructions.find((ix) => ix.data[0] === 26);
            (0, vitest_1.expect)(withdrawInstruction).toBeDefined();
            (0, vitest_1.expect)(withdrawInstruction?.keys).toHaveLength(16);
            (0, vitest_1.expect)(instructions.find((ix) => ix.data[0] === 3)).toBeUndefined();
        });
        (0, vitest_1.it)("should fall back to the legacy withdraw instruction when idempotent is false", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.withdrawSpl)(owner, mint, 1n, {
                idempotent: false,
            });
            (0, vitest_1.expect)(instructions).toHaveLength(1);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(3);
        });
    });
    (0, vitest_1.describe)("lamportsDelegatedTransferIx (Ephemeral SPL Token Program)", () => {
        const payer = web3_js_1.Keypair.generate().publicKey;
        const destination = web3_js_1.Keypair.generate().publicKey;
        const salt = new Uint8Array(Array.from({ length: 32 }, (_, i) => i));
        (0, vitest_1.it)("should derive the lamports PDA and encode the sponsored delegated transfer instruction", () => {
            const [rentPda] = (0, ephemeral_spl_token_program_1.deriveRentPda)();
            const [lamportsPda] = (0, ephemeral_spl_token_program_1.deriveLamportsPda)(payer, destination, salt);
            const destinationDelegationRecord = (0, pda_1.delegationRecordPdaFromDelegatedAccount)(destination);
            const instruction = (0, ephemeral_spl_token_program_1.lamportsDelegatedTransferIx)(payer, destination, 25n, salt);
            (0, vitest_1.expect)(instruction.programId.toBase58()).toBe(constants_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID.toBase58());
            (0, vitest_1.expect)(instruction.keys).toHaveLength(11);
            (0, vitest_1.expect)(instruction.keys[0]).toMatchObject({
                pubkey: payer,
                isSigner: true,
                isWritable: true,
            });
            (0, vitest_1.expect)(instruction.keys[1].pubkey.toBase58()).toBe(rentPda.toBase58());
            (0, vitest_1.expect)(instruction.keys[2].pubkey.toBase58()).toBe(lamportsPda.toBase58());
            (0, vitest_1.expect)(instruction.keys[9]).toMatchObject({
                pubkey: destination,
                isSigner: false,
                isWritable: true,
            });
            (0, vitest_1.expect)(instruction.keys[10]).toMatchObject({
                pubkey: destinationDelegationRecord,
                isSigner: false,
                isWritable: false,
            });
            const data = Buffer.from(instruction.data);
            (0, vitest_1.expect)(data[0]).toBe(20);
            (0, vitest_1.expect)(data.readBigUInt64LE(1)).toBe(25n);
            (0, vitest_1.expect)(Buffer.from(data.subarray(9, 41)).equals(Buffer.from(salt))).toBe(true);
            (0, vitest_1.expect)(data).toHaveLength(41);
        });
    });
    (0, vitest_1.describe)("transferSpl (Ephemeral SPL Token Program)", () => {
        const from = web3_js_1.Keypair.generate().publicKey;
        const to = web3_js_1.Keypair.generate().publicKey;
        const mint = web3_js_1.Keypair.generate().publicKey;
        const validator = web3_js_1.Keypair.generate().publicKey;
        (0, vitest_1.it)("should use the shuttle private transfer instruction for private base-to-base transfers", async () => {
            const [queue] = (0, ephemeral_spl_token_program_1.deriveTransferQueue)(mint, validator);
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "private",
                fromBalance: "base",
                toBalance: "base",
                validator,
                shuttleId: 7,
                privateTransfer: {
                    minDelayMs: 100n,
                    maxDelayMs: 300n,
                    split: 4,
                },
            });
            (0, vitest_1.expect)(instructions).toHaveLength(2);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(28);
            (0, vitest_1.expect)(instructions[0].keys[1].pubkey.toBase58()).toBe(queue.toBase58());
            const data = Buffer.from(instructions[1].data);
            (0, vitest_1.expect)(data[0]).toBe(25);
            (0, vitest_1.expect)(instructions[1].keys).toHaveLength(19);
            (0, vitest_1.expect)(data.readUInt32LE(1)).toBe(7);
            (0, vitest_1.expect)(data.readBigUInt64LE(5)).toBe(25n);
            const [validatorField, nextOffset] = readLengthPrefixedField(data, 13);
            const [destinationField, suffixOffset] = readLengthPrefixedField(data, nextOffset);
            const [suffixField, endOffset] = readLengthPrefixedField(data, suffixOffset);
            (0, vitest_1.expect)(validatorField.equals(validator.toBuffer())).toBe(true);
            (0, vitest_1.expect)(destinationField).toHaveLength(80);
            (0, vitest_1.expect)(suffixField).toHaveLength(68);
            (0, vitest_1.expect)(endOffset).toBe(data.length);
        });
        (0, vitest_1.it)("should append clientRefId to the encrypted private transfer suffix when provided", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "private",
                fromBalance: "base",
                toBalance: "base",
                validator,
                shuttleId: 7,
                privateTransfer: {
                    minDelayMs: 100n,
                    maxDelayMs: 300n,
                    split: 4,
                    clientRefId: 42n,
                },
            });
            const data = Buffer.from(instructions[1].data);
            const [, nextOffset] = readLengthPrefixedField(data, 13);
            const [, suffixOffset] = readLengthPrefixedField(data, nextOffset);
            const [suffixField] = readLengthPrefixedField(data, suffixOffset);
            (0, vitest_1.expect)(suffixField).toHaveLength(76);
        });
        (0, vitest_1.it)("should initialize the destination ATA and vault when requested", async () => {
            const [vault] = (0, ephemeral_spl_token_program_1.deriveVault)(mint);
            const [vaultEphemeralAta] = (0, ephemeral_spl_token_program_1.deriveEphemeralAta)(vault, mint);
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "private",
                fromBalance: "base",
                toBalance: "base",
                validator,
                shuttleId: 7,
                initIfMissing: true,
                initVaultIfMissing: true,
                privateTransfer: {
                    minDelayMs: 100n,
                    maxDelayMs: 300n,
                    split: 4,
                },
            });
            (0, vitest_1.expect)(instructions).toHaveLength(5);
            (0, vitest_1.expect)(instructions[2].keys[1].pubkey.toBase58()).toBe(vaultEphemeralAta.toBase58());
            (0, vitest_1.expect)(instructions[2].data[0]).toBe(4);
            (0, vitest_1.expect)(instructions[3].data[0]).toBe(28);
            (0, vitest_1.expect)(instructions[4].data[0]).toBe(25);
        });
        (0, vitest_1.it)("should prepend source ATA creation when initAtasIfMissing is set on base-source transfers", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "public",
                fromBalance: "base",
                toBalance: "base",
                initAtasIfMissing: true,
            });
            (0, vitest_1.expect)(instructions).toHaveLength(2);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(1);
            (0, vitest_1.expect)(instructions[0].keys[2].pubkey.toBase58()).toBe(from.toBase58());
            (0, vitest_1.expect)(instructions[1].data[0]).toBe(3);
        });
        (0, vitest_1.it)("should use the shuttle merge instruction for private base-to-ephemeral transfers", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "private",
                fromBalance: "base",
                toBalance: "ephemeral",
                validator,
                shuttleId: 7,
            });
            (0, vitest_1.expect)(instructions).toHaveLength(1);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(24);
            (0, vitest_1.expect)(instructions[0].keys).toHaveLength(19);
            (0, vitest_1.expect)(Buffer.from(instructions[0].data).readBigUInt64LE(5)).toBe(25n);
        });
        (0, vitest_1.it)("should initialize and delegate the receiver eata for private base-to-ephemeral transfers when requested", async () => {
            const [toEphemeralAta] = (0, ephemeral_spl_token_program_1.deriveEphemeralAta)(to, mint);
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "private",
                fromBalance: "base",
                toBalance: "ephemeral",
                validator,
                shuttleId: 7,
                initIfMissing: true,
            });
            (0, vitest_1.expect)(instructions).toHaveLength(4);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(1);
            (0, vitest_1.expect)(instructions[0].keys[2].pubkey.toBase58()).toBe(to.toBase58());
            (0, vitest_1.expect)(instructions[1].data[0]).toBe(0);
            (0, vitest_1.expect)(instructions[1].keys[0].pubkey.toBase58()).toBe(toEphemeralAta.toBase58());
            (0, vitest_1.expect)(instructions[2].data[0]).toBe(4);
            (0, vitest_1.expect)(instructions[2].keys[1].pubkey.toBase58()).toBe(toEphemeralAta.toBase58());
            (0, vitest_1.expect)(instructions[3].data[0]).toBe(24);
        });
        (0, vitest_1.it)("should ignore initAtasIfMissing on ephemeral-source transfers", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "private",
                fromBalance: "ephemeral",
                toBalance: "base",
                validator,
                initAtasIfMissing: true,
                privateTransfer: {
                    minDelayMs: 100n,
                    maxDelayMs: 300n,
                    split: 4,
                },
            });
            (0, vitest_1.expect)(instructions).toHaveLength(1);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(16);
        });
        (0, vitest_1.it)("should use depositAndQueueTransferIx for private ephemeral-to-base transfers", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "private",
                fromBalance: "ephemeral",
                toBalance: "base",
                validator,
                initIfMissing: true,
                initVaultIfMissing: true,
                privateTransfer: {
                    minDelayMs: 100n,
                    maxDelayMs: 300n,
                    split: 4,
                },
            });
            (0, vitest_1.expect)(instructions).toHaveLength(1);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(16);
            (0, vitest_1.expect)(instructions[0].keys).toHaveLength(9);
            (0, vitest_1.expect)(instructions[0].keys[5].pubkey.toBase58()).toBe(to.toBase58());
            (0, vitest_1.expect)(instructions[0].keys[8].pubkey.toBase58()).toBe(instructions[0].keys[3].pubkey.toBase58());
            (0, vitest_1.expect)(Buffer.from(instructions[0].data).readBigUInt64LE(1)).toBe(25n);
            (0, vitest_1.expect)(Buffer.from(instructions[0].data).readBigUInt64LE(9)).toBe(100n);
            (0, vitest_1.expect)(Buffer.from(instructions[0].data).readBigUInt64LE(17)).toBe(300n);
            (0, vitest_1.expect)(Buffer.from(instructions[0].data).readUInt32LE(25)).toBe(4);
        });
        (0, vitest_1.it)("should require validator for private ephemeral-to-base transfers", async () => {
            await (0, vitest_1.expect)((0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "private",
                fromBalance: "ephemeral",
                toBalance: "base",
            })).rejects.toThrow("validator is required for private ephemeral-to-base transfers");
        });
        (0, vitest_1.it)("should use a normal transfer for public base-to-base transfers", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "public",
                fromBalance: "base",
                toBalance: "base",
            });
            (0, vitest_1.expect)(instructions).toHaveLength(1);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(3);
            (0, vitest_1.expect)(instructions[0].keys).toHaveLength(3);
            (0, vitest_1.expect)(Buffer.from(instructions[0].data).readBigUInt64LE(1)).toBe(25n);
        });
        (0, vitest_1.it)("should not prepend refill for public base-to-base transfers even when validator is provided", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "public",
                fromBalance: "base",
                toBalance: "base",
                validator,
            });
            (0, vitest_1.expect)(instructions).toHaveLength(1);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(3);
            (0, vitest_1.expect)(instructions[0].keys).toHaveLength(3);
        });
        (0, vitest_1.it)("should use a normal transfer for public ephemeral-to-ephemeral transfers", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "public",
                fromBalance: "ephemeral",
                toBalance: "ephemeral",
            });
            (0, vitest_1.expect)(instructions).toHaveLength(1);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(3);
            (0, vitest_1.expect)(instructions[0].keys).toHaveLength(3);
            (0, vitest_1.expect)(Buffer.from(instructions[0].data).readBigUInt64LE(1)).toBe(25n);
        });
        (0, vitest_1.it)("should use a normal transfer for private ephemeral-to-ephemeral transfers", async () => {
            const instructions = await (0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "private",
                fromBalance: "ephemeral",
                toBalance: "ephemeral",
                initIfMissing: true,
                initVaultIfMissing: true,
            });
            (0, vitest_1.expect)(instructions).toHaveLength(1);
            (0, vitest_1.expect)(instructions[0].data[0]).toBe(3);
            (0, vitest_1.expect)(instructions[0].keys).toHaveLength(3);
            (0, vitest_1.expect)(Buffer.from(instructions[0].data).readBigUInt64LE(1)).toBe(25n);
        });
        (0, vitest_1.it)("should reject unsupported routes", async () => {
            await (0, vitest_1.expect)((0, ephemeral_spl_token_program_1.transferSpl)(from, to, mint, 25n, {
                visibility: "public",
                fromBalance: "base",
                toBalance: "ephemeral",
            })).rejects.toThrow("transferSpl route not implemented: visibility=public, fromBalance=base, toBalance=ephemeral");
        });
    });
    (0, vitest_1.describe)("ensureTransferQueueCrankIx (Ephemeral SPL Token Program)", () => {
        const payer = mockPublicKey;
        const queue = differentKey;
        const magicFeeVault = new web3_js_1.PublicKey("11111111111111111111111111111113");
        (0, vitest_1.it)("should include queue, magic fee vault, magic context, and magic program in order", () => {
            const instruction = (0, ephemeral_spl_token_program_1.ensureTransferQueueCrankIx)(payer, queue, magicFeeVault);
            (0, vitest_1.expect)(instruction).toBeInstanceOf(web3_js_1.TransactionInstruction);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(5);
            (0, vitest_1.expect)(instruction.keys[0].pubkey.toBase58()).toBe(payer.toBase58());
            (0, vitest_1.expect)(instruction.keys[1].pubkey.toBase58()).toBe(queue.toBase58());
            (0, vitest_1.expect)(instruction.keys[2].pubkey.toBase58()).toBe(magicFeeVault.toBase58());
            (0, vitest_1.expect)(instruction.keys[3].pubkey.toBase58()).toBe(constants_1.MAGIC_CONTEXT_ID.toBase58());
            (0, vitest_1.expect)(instruction.keys[4].pubkey.toBase58()).toBe(constants_1.MAGIC_PROGRAM_ID.toBase58());
        });
    });
    (0, vitest_1.describe)("depositAndQueueTransferIx (Ephemeral SPL Token Program)", () => {
        const queue = differentKey;
        const vault = new web3_js_1.PublicKey("11111111111111111111111111111113");
        const mint = new web3_js_1.PublicKey("11111111111111111111111111111114");
        const source = new web3_js_1.PublicKey("11111111111111111111111111111115");
        const vaultAta = new web3_js_1.PublicKey("11111111111111111111111111111116");
        const destination = new web3_js_1.PublicKey("11111111111111111111111111111117");
        (0, vitest_1.it)("should serialize min/max delay ms and split", () => {
            const instruction = (0, ephemeral_spl_token_program_1.depositAndQueueTransferIx)(queue, vault, mint, source, vaultAta, destination, mockPublicKey, 25n, 100n, 300n, 4);
            (0, vitest_1.expect)(instruction).toBeInstanceOf(web3_js_1.TransactionInstruction);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(9);
            (0, vitest_1.expect)(instruction.keys[8].pubkey.toBase58()).toBe(source.toBase58());
            (0, vitest_1.expect)(instruction.keys[8].isWritable).toBe(true);
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([
                16,
                ...Array.from(Buffer.from([25n, 100n, 300n].flatMap((value) => {
                    const out = Buffer.alloc(8);
                    out.writeBigUInt64LE(value);
                    return Array.from(out);
                }))),
                4,
                0,
                0,
                0,
            ]);
        });
        (0, vitest_1.it)("should allow overriding the reimbursement token account", () => {
            const reimbursementTokenInfo = new web3_js_1.PublicKey("11111111111111111111111111111118");
            const instruction = (0, ephemeral_spl_token_program_1.depositAndQueueTransferIx)(queue, vault, mint, source, vaultAta, destination, mockPublicKey, 25n, 100n, 300n, 4, reimbursementTokenInfo);
            (0, vitest_1.expect)(instruction.keys[8].pubkey.toBase58()).toBe(reimbursementTokenInfo.toBase58());
        });
        (0, vitest_1.it)("should append clientRefId when provided", () => {
            const instruction = (0, ephemeral_spl_token_program_1.depositAndQueueTransferIx)(queue, vault, mint, source, vaultAta, destination, mockPublicKey, 25n, 100n, 300n, 4, source, 42n);
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([
                16,
                ...Array.from(Buffer.from([25n, 100n, 300n].flatMap((value) => {
                    const out = Buffer.alloc(8);
                    out.writeBigUInt64LE(value);
                    return Array.from(out);
                }))),
                4,
                0,
                0,
                0,
                ...Array.from((() => {
                    const out = Buffer.alloc(8);
                    out.writeBigUInt64LE(42n);
                    return out;
                })()),
            ]);
        });
    });
    (0, vitest_1.describe)("undelegateAndCloseShuttleEphemeralAtaIx (Ephemeral SPL Token Program)", () => {
        (0, vitest_1.it)("should include rent reimbursement and destination ATA accounts", () => {
            const rentReimbursement = new web3_js_1.PublicKey("11111111111111111111111111111113");
            const shuttleEphemeralAta = new web3_js_1.PublicKey("11111111111111111111111111111114");
            const shuttleAta = new web3_js_1.PublicKey("11111111111111111111111111111115");
            const shuttleWalletAta = new web3_js_1.PublicKey("11111111111111111111111111111116");
            const destinationAta = new web3_js_1.PublicKey("11111111111111111111111111111117");
            const instruction = (0, ephemeral_spl_token_program_1.undelegateAndCloseShuttleEphemeralAtaIx)(mockPublicKey, rentReimbursement, shuttleEphemeralAta, shuttleAta, shuttleWalletAta, destinationAta, 3);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(9);
            (0, vitest_1.expect)(instruction.keys[1].pubkey.toBase58()).toBe(rentReimbursement.toBase58());
            (0, vitest_1.expect)(instruction.keys[1].isWritable).toBe(true);
            (0, vitest_1.expect)(instruction.keys[5].pubkey.toBase58()).toBe(destinationAta.toBase58());
            (0, vitest_1.expect)(instruction.keys[5].isWritable).toBe(true);
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([14, 3]);
        });
    });
    (0, vitest_1.describe)("delegateTransferQueueIx (Ephemeral SPL Token Program)", () => {
        const payer = mockPublicKey;
        const queue = differentKey;
        (0, vitest_1.it)("should serialize discriminator 19 for the delegated transfer queue opcode", () => {
            const instruction = (0, ephemeral_spl_token_program_1.delegateTransferQueueIx)(queue, payer, mockPublicKey);
            (0, vitest_1.expect)(instruction).toBeInstanceOf(web3_js_1.TransactionInstruction);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(9);
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([19]);
        });
    });
    (0, vitest_1.describe)("transfer queue helpers (Ephemeral SPL Token Program)", () => {
        const mint = new web3_js_1.PublicKey("11111111111111111111111111111113");
        const validator = new web3_js_1.PublicKey("11111111111111111111111111111114");
        (0, vitest_1.it)("should derive validator-scoped transfer queue PDAs", () => {
            const [queueA] = (0, ephemeral_spl_token_program_1.deriveTransferQueue)(mint, validator);
            const [queueB] = (0, ephemeral_spl_token_program_1.deriveTransferQueue)(mint, mockPublicKey);
            (0, vitest_1.expect)(queueA.toBase58()).not.toBe(queueB.toBase58());
        });
        (0, vitest_1.it)("should include validator and requested item count in initTransferQueueIx", () => {
            const [queue] = (0, ephemeral_spl_token_program_1.deriveTransferQueue)(mint, validator);
            const instruction = (0, ephemeral_spl_token_program_1.initTransferQueueIx)(mockPublicKey, queue, mint, validator, 92);
            (0, vitest_1.expect)(instruction).toBeInstanceOf(web3_js_1.TransactionInstruction);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(7);
            (0, vitest_1.expect)(instruction.keys[2].pubkey.toBase58()).toBe((0, pda_1.permissionPdaFromAccount)(queue).toBase58());
            (0, vitest_1.expect)(instruction.keys[4].pubkey.toBase58()).toBe(validator.toBase58());
            (0, vitest_1.expect)(instruction.keys[6].pubkey.toBase58()).toBe(constants_1.PERMISSION_PROGRAM_ID.toBase58());
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([12, 92, 0, 0, 0]);
        });
        (0, vitest_1.it)("should serialize discriminator 27 for allocateTransferQueueIx", () => {
            const [queue] = (0, ephemeral_spl_token_program_1.deriveTransferQueue)(mint, validator);
            const instruction = (0, ephemeral_spl_token_program_1.allocateTransferQueueIx)(queue);
            (0, vitest_1.expect)(instruction).toBeInstanceOf(web3_js_1.TransactionInstruction);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(2);
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([27]);
        });
        (0, vitest_1.it)("should derive the sponsored refill accounts for processPendingTransferQueueRefillIx", () => {
            const [queue] = (0, ephemeral_spl_token_program_1.deriveTransferQueue)(mint, validator);
            const instruction = (0, ephemeral_spl_token_program_1.processPendingTransferQueueRefillIx)(queue);
            const [rentPda] = (0, ephemeral_spl_token_program_1.deriveRentPda)();
            const [refillState] = web3_js_1.PublicKey.findProgramAddressSync([Buffer.from("queue-refill"), queue.toBuffer()], constants_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID);
            const [lamportsPda] = (0, ephemeral_spl_token_program_1.deriveLamportsPda)(rentPda, queue, queue.toBuffer());
            (0, vitest_1.expect)(instruction).toBeInstanceOf(web3_js_1.TransactionInstruction);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(11);
            (0, vitest_1.expect)(instruction.keys[0].pubkey.toBase58()).toBe(refillState.toBase58());
            (0, vitest_1.expect)(instruction.keys[1].pubkey.toBase58()).toBe(queue.toBase58());
            (0, vitest_1.expect)(instruction.keys[2].pubkey.toBase58()).toBe(rentPda.toBase58());
            (0, vitest_1.expect)(instruction.keys[3].pubkey.toBase58()).toBe(lamportsPda.toBase58());
            (0, vitest_1.expect)(instruction.keys[4].pubkey.toBase58()).toBe(constants_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID.toBase58());
            (0, vitest_1.expect)(instruction.keys[5].pubkey.toBase58()).toBe((0, pda_1.delegateBufferPdaFromDelegatedAccountAndOwnerProgram)(lamportsPda, constants_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID).toBase58());
            (0, vitest_1.expect)(instruction.keys[6].pubkey.toBase58()).toBe((0, pda_1.delegationRecordPdaFromDelegatedAccount)(lamportsPda).toBase58());
            (0, vitest_1.expect)(instruction.keys[7].pubkey.toBase58()).toBe((0, pda_1.delegationMetadataPdaFromDelegatedAccount)(lamportsPda).toBase58());
            (0, vitest_1.expect)(instruction.keys[8].pubkey.toBase58()).toBe(constants_1.DELEGATION_PROGRAM_ID.toBase58());
            (0, vitest_1.expect)(instruction.keys[9].pubkey.toBase58()).toBe(web3_js_1.SystemProgram.programId.toBase58());
            (0, vitest_1.expect)(instruction.keys[10].pubkey.toBase58()).toBe((0, pda_1.delegationRecordPdaFromDelegatedAccount)(queue).toBase58());
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([28]);
        });
    });
    (0, vitest_1.describe)("delegateEataPermissionIx (Ephemeral SPL Token Program)", () => {
        (0, vitest_1.it)("should serialize only the discriminator", () => {
            const instruction = (0, ephemeral_spl_token_program_1.delegateEataPermissionIx)(mockPublicKey, differentKey, mockPublicKey);
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([7]);
        });
    });
    (0, vitest_1.describe)("initEphemeralAtaIx (Ephemeral SPL Token Program)", () => {
        (0, vitest_1.it)("should serialize only the discriminator", () => {
            const instruction = (0, ephemeral_spl_token_program_1.initEphemeralAtaIx)(mockPublicKey, differentKey, mockPublicKey, differentKey);
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([0]);
        });
    });
    (0, vitest_1.describe)("initVaultIx (Ephemeral SPL Token Program)", () => {
        (0, vitest_1.it)("should serialize only the discriminator", () => {
            const vault = new web3_js_1.PublicKey("11111111111111111111111111111113");
            const mint = new web3_js_1.PublicKey("11111111111111111111111111111114");
            const payer = new web3_js_1.PublicKey("11111111111111111111111111111115");
            const instruction = (0, ephemeral_spl_token_program_1.initVaultIx)(vault, mint, payer);
            (0, vitest_1.expect)(Array.from(instruction.data)).toEqual([1]);
            (0, vitest_1.expect)(instruction.keys[3].pubkey.toBase58()).toBe((0, ephemeral_spl_token_program_1.deriveEphemeralAta)(vault, mint)[0].toBase58());
        });
    });
    (0, vitest_1.describe)("withdrawSplIx (Ephemeral SPL Token Program)", () => {
        (0, vitest_1.it)("should encode only discriminator plus amount", () => {
            const owner = new web3_js_1.PublicKey("11111111111111111111111111111113");
            const mint = new web3_js_1.PublicKey("11111111111111111111111111111114");
            const instruction = (0, ephemeral_spl_token_program_1.withdrawSplIx)(owner, mint, 1n);
            (0, vitest_1.expect)(instruction.data).toHaveLength(9);
            (0, vitest_1.expect)(instruction.data[0]).toBe(3);
            (0, vitest_1.expect)(Buffer.from(instruction.data).readBigUInt64LE(1)).toBe(1n);
        });
    });
    (0, vitest_1.describe)("schedulePrivateTransferIx (Ephemeral SPL Token Program)", () => {
        const user = new web3_js_1.PublicKey("11111111111111111111111111111113");
        const mint = new web3_js_1.PublicKey("11111111111111111111111111111114");
        const destinationOwner = new web3_js_1.PublicKey("11111111111111111111111111111115");
        const validator = web3_js_1.Keypair.generate().publicKey;
        const tokenProgram = new web3_js_1.PublicKey("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb");
        (0, vitest_1.it)("should build a 7-account ix with the right layout", () => {
            const instruction = (0, ephemeral_spl_token_program_1.schedulePrivateTransferIx)(user, mint, 7, destinationOwner, 100n, 300n, 4, validator);
            (0, vitest_1.expect)(instruction.programId.toBase58()).toBe(constants_1.EPHEMERAL_SPL_TOKEN_PROGRAM_ID.toBase58());
            (0, vitest_1.expect)(instruction.keys).toHaveLength(7);
            const [stashPda] = (0, ephemeral_spl_token_program_1.deriveStashPda)(user, mint);
            const [rentPda] = (0, ephemeral_spl_token_program_1.deriveRentPda)();
            const [hydraCrankPda] = (0, ephemeral_spl_token_program_1.deriveHydraCrankPda)(stashPda, 7);
            (0, vitest_1.expect)(instruction.keys[0].pubkey.toBase58()).toBe(user.toBase58());
            (0, vitest_1.expect)(instruction.keys[0].isSigner).toBe(true);
            (0, vitest_1.expect)(instruction.keys[0].isWritable).toBe(true);
            (0, vitest_1.expect)(instruction.keys[1].pubkey.toBase58()).toBe(stashPda.toBase58());
            (0, vitest_1.expect)(instruction.keys[1].isWritable).toBe(true);
            (0, vitest_1.expect)(instruction.keys[2].pubkey.toBase58()).toBe(rentPda.toBase58());
            (0, vitest_1.expect)(instruction.keys[2].isWritable).toBe(true);
            (0, vitest_1.expect)(instruction.keys[3].pubkey.toBase58()).toBe(hydraCrankPda.toBase58());
            (0, vitest_1.expect)(instruction.keys[3].isWritable).toBe(true);
            (0, vitest_1.expect)(instruction.keys[4].pubkey.toBase58()).toBe(constants_1.HYDRA_PROGRAM_ID.toBase58());
            (0, vitest_1.expect)(instruction.keys[5].pubkey.toBase58()).toBe(web3_js_1.SystemProgram.programId.toBase58());
            const data = Buffer.from(instruction.data);
            (0, vitest_1.expect)(data[0]).toBe(30);
            (0, vitest_1.expect)(data.readUInt32LE(1)).toBe(7);
            (0, vitest_1.expect)(data.subarray(6, 38).equals(mint.toBuffer())).toBe(true);
            const [validatorField, nextOffset] = readLengthPrefixedField(data, 48);
            const [destinationField, suffixOffset] = readLengthPrefixedField(data, nextOffset);
            const [suffixField, endOffset] = readLengthPrefixedField(data, suffixOffset);
            (0, vitest_1.expect)(validatorField.equals(validator.toBuffer())).toBe(true);
            (0, vitest_1.expect)(destinationField).toHaveLength(80);
            (0, vitest_1.expect)(suffixField).toHaveLength(68);
            (0, vitest_1.expect)(endOffset).toBe(data.length);
        });
        (0, vitest_1.it)("should lengthen the encrypted suffix when clientRefId is provided", () => {
            const instruction = (0, ephemeral_spl_token_program_1.schedulePrivateTransferIx)(user, mint, 7, destinationOwner, 100n, 300n, 4, validator, undefined, 42n);
            const data = Buffer.from(instruction.data);
            const [, afterValidator] = readLengthPrefixedField(data, 48);
            const [, afterDestination] = readLengthPrefixedField(data, afterValidator);
            const [suffixField] = readLengthPrefixedField(data, afterDestination);
            (0, vitest_1.expect)(suffixField).toHaveLength(76);
        });
        (0, vitest_1.it)("should accept a token program override when clientRefId is omitted", () => {
            const instruction = (0, ephemeral_spl_token_program_1.schedulePrivateTransferIx)(user, mint, 7, destinationOwner, 100n, 300n, 4, validator, tokenProgram);
            (0, vitest_1.expect)(instruction.keys[6].pubkey.toBase58()).toBe(tokenProgram.toBase58());
        });
        (0, vitest_1.it)("should still accept both clientRefId and token program override", () => {
            const instruction = (0, ephemeral_spl_token_program_1.schedulePrivateTransferIx)(user, mint, 7, destinationOwner, 100n, 300n, 4, validator, tokenProgram, 42n);
            (0, vitest_1.expect)(instruction.keys[6].pubkey.toBase58()).toBe(tokenProgram.toBase58());
            const data = Buffer.from(instruction.data);
            const [, afterValidator] = readLengthPrefixedField(data, 48);
            const [, afterDestination] = readLengthPrefixedField(data, afterValidator);
            const [suffixField] = readLengthPrefixedField(data, afterDestination);
            (0, vitest_1.expect)(suffixField).toHaveLength(76);
        });
        (0, vitest_1.it)("should reject non-u32 shuttle ids", () => {
            (0, vitest_1.expect)(() => (0, ephemeral_spl_token_program_1.schedulePrivateTransferIx)(user, mint, 4294967296, destinationOwner, 100n, 300n, 4, validator)).toThrowError(/shuttleId must fit in u32/);
        });
        (0, vitest_1.it)("should reject maxDelayMs < minDelayMs", () => {
            (0, vitest_1.expect)(() => (0, ephemeral_spl_token_program_1.schedulePrivateTransferIx)(user, mint, 7, destinationOwner, 500n, 100n, 4, validator)).toThrowError(/maxDelayMs must be greater than or equal to minDelayMs/);
        });
        (0, vitest_1.it)("should reject delays and clientRefId that exceed u64", () => {
            (0, vitest_1.expect)(() => (0, ephemeral_spl_token_program_1.schedulePrivateTransferIx)(user, mint, 7, destinationOwner, 0n, 0x10000000000000000n, 4, validator)).toThrowError(/delays and clientRefId must fit in u64/);
            (0, vitest_1.expect)(() => (0, ephemeral_spl_token_program_1.schedulePrivateTransferIx)(user, mint, 7, destinationOwner, 100n, 300n, 4, validator, undefined, 0x10000000000000000n)).toThrowError(/delays and clientRefId must fit in u64/);
        });
    });
});
//# sourceMappingURL=instructions.test.js.map