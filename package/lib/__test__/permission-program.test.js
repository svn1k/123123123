"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const vitest_1 = require("vitest");
const web3_js_1 = require("@solana/web3.js");
const permission_program_1 = require("../instructions/permission-program");
const constants_1 = require("../constants");
const pda_1 = require("../pda");
const types_1 = require("../access-control/types");
(0, vitest_1.describe)("Permission Program Instructions (web3.js)", () => {
    const testAuthority = new web3_js_1.PublicKey("11111111111111111111111111111113");
    const testMember = new web3_js_1.PublicKey("11111111111111111111111111111112");
    (0, vitest_1.describe)("createPermission instruction", () => {
        (0, vitest_1.it)("should create a createPermission instruction with valid parameters", () => {
            const instruction = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, {
                members: [
                    { pubkey: testAuthority, flags: types_1.AUTHORITY_FLAG },
                    { pubkey: testMember, flags: 0 },
                ],
            });
            (0, vitest_1.expect)(instruction.programId.equals(constants_1.PERMISSION_PROGRAM_ID)).toBe(true);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(4);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThan(0);
        });
        (0, vitest_1.it)("should serialize members correctly", () => {
            const members = [{ pubkey: testAuthority, flags: types_1.AUTHORITY_FLAG }];
            const instruction = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, { members });
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThanOrEqual(46);
        });
        (0, vitest_1.it)("should include permissionedAccount as readonly signer", () => {
            const instruction = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testMember,
            }, { members: null });
            const permissionedAccount = instruction.keys.find((key) => key.pubkey.equals(testAuthority));
            (0, vitest_1.expect)(permissionedAccount).toBeDefined();
            (0, vitest_1.expect)(permissionedAccount?.isWritable).toBe(false);
            (0, vitest_1.expect)(permissionedAccount?.isSigner).toBe(true);
        });
        (0, vitest_1.it)("should include payer as writable signer", () => {
            const payerAddress = new web3_js_1.PublicKey("11111111111111111111111111111115");
            const instruction = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: payerAddress,
            }, { members: null });
            const payerAccount = instruction.keys.find((key) => key.pubkey.equals(payerAddress));
            (0, vitest_1.expect)(payerAccount).toBeDefined();
            (0, vitest_1.expect)(payerAccount?.isWritable).toBe(true);
            (0, vitest_1.expect)(payerAccount?.isSigner).toBe(true);
        });
        (0, vitest_1.it)("should include permission PDA as writable", () => {
            const permissionedAccountAddress = new web3_js_1.PublicKey("11111111111111111111111111111116");
            const instruction = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: permissionedAccountAddress,
                payer: testMember,
            }, { members: null });
            const expectedPda = (0, pda_1.permissionPdaFromAccount)(permissionedAccountAddress);
            const permissionAccount = instruction.keys[1];
            (0, vitest_1.expect)(permissionAccount).toBeDefined();
            (0, vitest_1.expect)(permissionAccount.pubkey.equals(expectedPda)).toBe(true);
            (0, vitest_1.expect)(permissionAccount.isWritable).toBe(true);
            (0, vitest_1.expect)(permissionAccount.isSigner).toBe(false);
        });
        (0, vitest_1.it)("should include system program", () => {
            const instruction = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, { members: null });
            const systemProgram = instruction.keys.find((key) => key.pubkey.toBase58() === "11111111111111111111111111111111");
            (0, vitest_1.expect)(systemProgram).toBeDefined();
            (0, vitest_1.expect)(systemProgram?.isWritable).toBe(false);
            (0, vitest_1.expect)(systemProgram?.isSigner).toBe(false);
        });
        (0, vitest_1.it)("should handle empty members list", () => {
            const instruction = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, { members: [] });
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThanOrEqual(13);
        });
        (0, vitest_1.it)("should handle multiple members", () => {
            const members = [
                { pubkey: testAuthority, flags: types_1.AUTHORITY_FLAG },
                { pubkey: testMember, flags: 0 },
                {
                    pubkey: new web3_js_1.PublicKey("11111111111111111111111111111111"),
                    flags: types_1.AUTHORITY_FLAG,
                },
            ];
            const instruction = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, { members });
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            const expectedSize = 8 + 1 + 4 + members.length * 33;
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThanOrEqual(expectedSize);
        });
        (0, vitest_1.it)("should use discriminator [0, 0, 0, 0, 0, 0, 0, 0]", () => {
            const instruction = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, { members: null });
            (0, vitest_1.expect)(instruction.data[0]).toBe(0);
            (0, vitest_1.expect)(instruction.data[1]).toBe(0);
            (0, vitest_1.expect)(instruction.data[2]).toBe(0);
            (0, vitest_1.expect)(instruction.data[3]).toBe(0);
            (0, vitest_1.expect)(instruction.data[4]).toBe(0);
            (0, vitest_1.expect)(instruction.data[5]).toBe(0);
            (0, vitest_1.expect)(instruction.data[6]).toBe(0);
            (0, vitest_1.expect)(instruction.data[7]).toBe(0);
        });
        (0, vitest_1.it)("should encode authority flag correctly", () => {
            const authorityMember = {
                pubkey: testAuthority,
                flags: types_1.AUTHORITY_FLAG,
            };
            const nonAuthorityMember = {
                pubkey: testMember,
                flags: 0,
            };
            const instruction1 = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, { members: [authorityMember] });
            const instruction2 = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, { members: [nonAuthorityMember] });
            const authorityFlagIndex = 8 + 1 + 4;
            (0, vitest_1.expect)(instruction1.data[authorityFlagIndex]).toBe(1);
            (0, vitest_1.expect)(instruction2.data[authorityFlagIndex]).toBe(0);
        });
    });
    (0, vitest_1.describe)("updatePermission instruction", () => {
        (0, vitest_1.it)("should create an updatePermission instruction with valid parameters", () => {
            const instruction = (0, permission_program_1.createUpdatePermissionInstruction)({
                authority: [testAuthority, true],
                permissionedAccount: [testAuthority, true],
            }, {
                members: [
                    { pubkey: testAuthority, flags: types_1.AUTHORITY_FLAG },
                    { pubkey: testMember, flags: 0 },
                ],
            });
            (0, vitest_1.expect)(instruction.programId.equals(constants_1.PERMISSION_PROGRAM_ID)).toBe(true);
            (0, vitest_1.expect)(instruction.keys).toHaveLength(3);
            (0, vitest_1.expect)(instruction.data).toBeDefined();
        });
        (0, vitest_1.it)("should include authority as signer", () => {
            const authorityAddress = new web3_js_1.PublicKey("11111111111111111111111111111113");
            const instruction = (0, permission_program_1.createUpdatePermissionInstruction)({
                authority: [authorityAddress, true],
                permissionedAccount: [testAuthority, false],
            }, { members: null });
            const authorityAccount = instruction.keys.find((key) => key.pubkey.equals(authorityAddress));
            (0, vitest_1.expect)(authorityAccount).toBeDefined();
            (0, vitest_1.expect)(authorityAccount?.isWritable).toBe(false);
            (0, vitest_1.expect)(authorityAccount?.isSigner).toBe(true);
        });
        (0, vitest_1.it)("should include permissionedAccount as signer", () => {
            const permissionedAddress = new web3_js_1.PublicKey("11111111111111111111111111111114");
            const instruction = (0, permission_program_1.createUpdatePermissionInstruction)({
                authority: [testAuthority, false],
                permissionedAccount: [permissionedAddress, true],
            }, { members: null });
            const permissionedAccount = instruction.keys.find((key) => key.pubkey.equals(permissionedAddress));
            (0, vitest_1.expect)(permissionedAccount).toBeDefined();
            (0, vitest_1.expect)(permissionedAccount?.isWritable).toBe(false);
            (0, vitest_1.expect)(permissionedAccount?.isSigner).toBe(true);
        });
        (0, vitest_1.it)("should include permission PDA as writable at index 2", () => {
            const permissionedAccountAddress = new web3_js_1.PublicKey("11111111111111111111111111111117");
            const instruction = (0, permission_program_1.createUpdatePermissionInstruction)({
                authority: [testAuthority, false],
                permissionedAccount: [permissionedAccountAddress, true],
            }, { members: null });
            const expectedPda = (0, pda_1.permissionPdaFromAccount)(permissionedAccountAddress);
            const permissionAccount = instruction.keys[2];
            (0, vitest_1.expect)(permissionAccount).toBeDefined();
            (0, vitest_1.expect)(permissionAccount.pubkey.equals(expectedPda)).toBe(true);
            (0, vitest_1.expect)(permissionAccount.isWritable).toBe(true);
            (0, vitest_1.expect)(permissionAccount.isSigner).toBe(false);
        });
        (0, vitest_1.it)("should use discriminator [1, 0, 0, 0, 0, 0, 0, 0]", () => {
            const instruction = (0, permission_program_1.createUpdatePermissionInstruction)({
                authority: [testAuthority, true],
                permissionedAccount: [testAuthority, true],
            }, { members: null });
            (0, vitest_1.expect)(instruction.data[0]).toBe(1);
            (0, vitest_1.expect)(instruction.data[1]).toBe(0);
            (0, vitest_1.expect)(instruction.data[2]).toBe(0);
            (0, vitest_1.expect)(instruction.data[3]).toBe(0);
            (0, vitest_1.expect)(instruction.data[4]).toBe(0);
            (0, vitest_1.expect)(instruction.data[5]).toBe(0);
            (0, vitest_1.expect)(instruction.data[6]).toBe(0);
            (0, vitest_1.expect)(instruction.data[7]).toBe(0);
        });
        (0, vitest_1.it)("should handle empty members list", () => {
            const instruction = (0, permission_program_1.createUpdatePermissionInstruction)({
                authority: [testAuthority, true],
                permissionedAccount: [testAuthority, true],
            }, { members: [] });
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThanOrEqual(12);
        });
        (0, vitest_1.it)("should handle multiple members", () => {
            const members = [
                { pubkey: testAuthority, flags: types_1.AUTHORITY_FLAG },
                { pubkey: testMember, flags: 0 },
                {
                    pubkey: new web3_js_1.PublicKey("11111111111111111111111111111113"),
                    flags: types_1.AUTHORITY_FLAG,
                },
            ];
            const instruction = (0, permission_program_1.createUpdatePermissionInstruction)({
                authority: [testAuthority, true],
                permissionedAccount: [testAuthority, true],
            }, { members });
            (0, vitest_1.expect)(instruction.data).toBeDefined();
            const expectedSize = 8 + 4 + members.length * 33;
            (0, vitest_1.expect)(instruction.data.length).toBeGreaterThanOrEqual(expectedSize);
        });
    });
    (0, vitest_1.describe)("Cross-instruction consistency", () => {
        (0, vitest_1.it)("should all target the same permission program", () => {
            const createPermissionInstr = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, { members: null });
            const updatePermissionInstr = (0, permission_program_1.createUpdatePermissionInstruction)({
                authority: [testAuthority, true],
                permissionedAccount: [testAuthority, true],
            }, { members: null });
            (0, vitest_1.expect)(createPermissionInstr.programId.equals(constants_1.PERMISSION_PROGRAM_ID)).toBe(true);
            (0, vitest_1.expect)(updatePermissionInstr.programId.equals(constants_1.PERMISSION_PROGRAM_ID)).toBe(true);
        });
        (0, vitest_1.it)("should have unique discriminators", () => {
            const createPermissionInstr = (0, permission_program_1.createCreatePermissionInstruction)({
                permissionedAccount: testAuthority,
                payer: testAuthority,
            }, { members: null });
            const updatePermissionInstr = (0, permission_program_1.createUpdatePermissionInstruction)({
                authority: [testAuthority, true],
                permissionedAccount: [testAuthority, true],
            }, { members: null });
            const disc1 = createPermissionInstr.data[0];
            const disc2 = updatePermissionInstr.data[0];
            (0, vitest_1.expect)(disc1).not.toBe(disc2);
            (0, vitest_1.expect)(disc1).toBe(0);
            (0, vitest_1.expect)(disc2).toBe(1);
        });
    });
});
//# sourceMappingURL=permission-program.test.js.map