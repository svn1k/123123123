"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.encryptEd25519Recipient = encryptEd25519Recipient;
const blake2b_1 = require("@noble/hashes/blake2b");
const ed25519_1 = require("@noble/curves/ed25519");
const nacl = __importStar(require("tweetnacl"));
function encryptEd25519Recipient(plaintext, recipient) {
    const recipientX25519 = (0, ed25519_1.edwardsToMontgomeryPub)(recipient.toBytes());
    const ephemeral = nacl.box.keyPair();
    const nonce = (0, blake2b_1.blake2b)(Buffer.concat([
        Buffer.from(ephemeral.publicKey),
        Buffer.from(recipientX25519),
    ]), { dkLen: nacl.box.nonceLength });
    const ciphertext = nacl.box(plaintext, nonce, recipientX25519, ephemeral.secretKey);
    return Buffer.concat([
        Buffer.from(ephemeral.publicKey),
        Buffer.from(ciphertext),
    ]);
}
//# sourceMappingURL=crypto.js.map