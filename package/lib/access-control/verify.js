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
exports.verifyTeeRpcIntegrity = verifyTeeRpcIntegrity;
exports.verifyTeeIntegrity = verifyTeeIntegrity;
const sha2_1 = require("@noble/hashes/sha2");
const dcap_qvl_1 = require("@phala/dcap-qvl");
const nacl = __importStar(require("tweetnacl"));
async function verifyTeeRpcIntegrity(rpcUrl) {
    const challengeBytes = Buffer.from(Uint8Array.from(Array(64)
        .fill(0)
        .map(() => Math.floor(Math.random() * 256))));
    const challenge = challengeBytes.toString("base64");
    const url = `${rpcUrl}/quote?challenge=${encodeURIComponent(challenge)}`;
    const response = await fetch(url);
    const responseBody = await response.json();
    if (response.status !== 200 || !("quote" in responseBody)) {
        throw new Error(responseBody.error ?? "Failed to get quote");
    }
    const rawQuote = Uint8Array.from(Buffer.from(responseBody.quote, "base64"));
    const quote = await verifyQuote(rawQuote);
    if (!quote) {
        throw new Error("Invalid quote");
    }
    const td10 = quote.report.asTd10();
    const td15 = td10 ? null : quote.report.asTd15();
    const reportData = td10
        ? Buffer.from(td10.reportData)
        : td15
            ? Buffer.from(td15.base.reportData)
            : null;
    if (!reportData) {
        throw new Error("Unsupported quote report format");
    }
    if (!reportData.equals(challengeBytes)) {
        throw new Error("Quote reportData does not match challenge");
    }
}
async function verifyTeeIntegrity(rpcUrl) {
    const challengeBytes = Buffer.from(Uint8Array.from(Array(64)
        .fill(0)
        .map(() => Math.floor(Math.random() * 256))));
    const challenge = challengeBytes.toString("base64");
    const url = `${rpcUrl}/fast-quote?challenge=${encodeURIComponent(challenge)}`;
    const response = await fetch(url);
    const responseBody = await response.json();
    if (response.status !== 200 || !("quote" in responseBody)) {
        throw new Error(responseBody.error ?? "Failed to get quote");
    }
    const rawQuote = Uint8Array.from(Buffer.from(responseBody.quote, "base64"));
    const quote = await verifyQuote(rawQuote);
    if (!quote) {
        throw new Error("Invalid quote");
    }
    await verifyChallenge(responseBody, quote, challengeBytes);
}
async function verifyQuote(rawQuote) {
    const pccsUrl = "https://pccs.phala.network/tdx/certification/v4";
    const quoteCollateral = await (0, dcap_qvl_1.getCollateral)(pccsUrl, rawQuote);
    const now = Math.floor(Date.now() / 1000);
    (0, dcap_qvl_1.verify)(rawQuote, quoteCollateral, now);
    return dcap_qvl_1.Quote.parse(rawQuote);
}
async function verifyChallenge(response, parsedQuote, challengeBytes) {
    const msgBytes = Buffer.from(response.challenge, "base64");
    if (!msgBytes.equals(Buffer.from(challengeBytes))) {
        throw new Error("Invalid challenge");
    }
    const pk = Buffer.from(response.pubkey, "base64");
    if (pk.length !== 32) {
        throw new Error(`Invalid pubkey length: ${pk.length}`);
    }
    const sig = Buffer.from(response.signature, "base64");
    const okSig = nacl.sign.detached.verify(challengeBytes, sig, pk);
    if (!okSig) {
        throw new Error("Invalid signature");
    }
    const td = parsedQuote.report.asTd10();
    if (!td) {
        throw new Error("Not a TD10 quote");
    }
    const reportData = Buffer.from(td.reportData);
    if (reportData.length !== 64) {
        throw new Error(`Invalid reportData length: ${reportData.length}`);
    }
    const pubkeyHash = (0, sha2_1.sha512)(Uint8Array.from(pk));
    if (!reportData.subarray(0, 64).equals(Buffer.from(pubkeyHash))) {
        throw new Error(`Quote reportData mismatch: ${reportData.subarray(0, 64).toString("hex")} !== ${Buffer.from(pubkeyHash).toString("hex")}`);
    }
}
//# sourceMappingURL=verify.js.map