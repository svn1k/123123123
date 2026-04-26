export interface UndelegateArgs {
    pdaSeeds: number[][];
}
export type UndelegateArgsArgs = UndelegateArgs;
export declare function serializeUndelegateArgs(args: UndelegateArgsArgs): Buffer;
export declare function deserializeUndelegateArgs(buffer: Buffer, offset?: number): UndelegateArgs;
//# sourceMappingURL=undelegateArgs.d.ts.map