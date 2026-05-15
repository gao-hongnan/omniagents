# TypeScript Type-Safety — Canonical Examples

Working code patterns that conform to the rules in `../SKILL.md`. Every
example below is written to conform to TypeScript 6.0, `tsc --strict`, and
type-aware ESLint rules such as `strictTypeChecked`. They are illustrative,
not exhaustive.

## TypeScript 6.0 tsconfig baseline — explicit strict defaults

Write TS 6.0 defaults explicitly in shared configs so downstream packages do
not depend on moving compiler defaults. For packages that run directly in
Node.js, pair `module` and `moduleResolution` on NodeNext.

```jsonc
{
    "compilerOptions": {
        "target": "es2025",
        "module": "nodenext",
        "moduleResolution": "nodenext",
        "strict": true,
        "noUncheckedIndexedAccess": true,
        "exactOptionalPropertyTypes": true,
        "noImplicitOverride": true,
        "noFallthroughCasesInSwitch": true,
        "noPropertyAccessFromIndexSignature": true,
        "noUncheckedSideEffectImports": true,
        "verbatimModuleSyntax": true,
        "isolatedDeclarations": true,
        "rootDir": "./src",
        "outDir": "./dist",
        "types": ["node"],
        "paths": {
            "@app/*": ["./src/app/*"],
            "@lib/*": ["./src/lib/*"]
        }
    },
    "include": ["src/**/*.ts"]
}
```

For bundled apps, change only the resolver policy:

```jsonc
{
    "compilerOptions": {
        "module": "esnext",
        "moduleResolution": "bundler",
        "strict": true,
        "types": ["vite/client"]
    }
}
```

Rejected TS 6.0 migration shapes:

```jsonc
{
    "compilerOptions": {
        "ignoreDeprecations": "6.0",
        "baseUrl": "./src",
        "moduleResolution": "node",
        "types": ["*"]
    }
}
```

## Import attributes — use `with`, not `assert`

```typescript
import packageJson from "../package.json" with { type: "json" };

export const packageName: string = packageJson.name;
```

## Generic registry — type-safe key/value store

```typescript
export class Registry<TKey, TValue> {
    private readonly items = new Map<TKey, TValue>();

    register(key: TKey, value: TValue): void {
        this.items.set(key, value);
    }

    get(key: TKey): TValue | undefined {
        return this.items.get(key);
    }

    getOrThrow(key: TKey): TValue {
        const value = this.items.get(key);
        if (value === undefined) {
            throw new Error(`No item registered for key: ${String(key)}`);
        }
        return value;
    }

    entries(): IterableIterator<[TKey, TValue]> {
        return this.items.entries();
    }
}
```

## Plugin protocol with registry

```typescript
export interface Plugin<TContext = unknown> {
    readonly name: string;
    readonly version: string;
    initialize(context: TContext): Promise<void>;
    shutdown(): Promise<void>;
}

export class PluginRegistry<TContext> {
    private readonly plugins = new Map<string, Plugin<TContext>>();

    register(plugin: Plugin<TContext>): void {
        if (this.plugins.has(plugin.name)) {
            throw new Error(`Plugin "${plugin.name}" already registered`);
        }
        this.plugins.set(plugin.name, plugin);
    }

    async initializeAll(context: TContext): Promise<void> {
        for (const plugin of this.plugins.values()) {
            await plugin.initialize(context);
        }
    }
}
```

## Branded types for identifiers

```typescript
declare const __brand: unique symbol;
export type Brand<T, TName extends string> = T & { readonly [__brand]: TName };

export type UserId = Brand<string, "UserId">;
export type OrderId = Brand<string, "OrderId">;

export function createUserId(raw: string): UserId {
    if (!raw.startsWith("user_")) {
        throw new Error(`Invalid UserId: ${raw}`);
    }
    return raw as UserId;
}

// Compile error if a caller passes an OrderId where UserId is expected:
// declare function getUser(id: UserId): User;
// getUser(someOrderId);  // TS2345
```

## Discriminated union with exhaustiveness check

```typescript
export type AsyncState<TData, TError = Error> =
    | { status: "idle" }
    | { status: "loading" }
    | { status: "success"; data: TData }
    | { status: "error"; error: TError };

export function describe<TData>(state: AsyncState<TData>): string {
    switch (state.status) {
        case "idle":
            return "Idle";
        case "loading":
            return "Loading…";
        case "success":
            return `Loaded: ${JSON.stringify(state.data)}`;
        case "error":
            return `Error: ${state.error.message}`;
        default: {
            const _exhaustive: never = state;
            return _exhaustive;
        }
    }
}
```

## `Result<T, E>` for functional error handling

```typescript
export type Result<T, E = Error> =
    | { readonly ok: true; readonly value: T }
    | { readonly ok: false; readonly error: E };

export const Result = {
    ok<T>(value: T): Result<T, never> {
        return { ok: true, value };
    },
    err<E>(error: E): Result<never, E> {
        return { ok: false, error };
    },
    map<T, U, E>(result: Result<T, E>, fn: (value: T) => U): Result<U, E> {
        return result.ok ? Result.ok(fn(result.value)) : result;
    },
    unwrapOr<T, E>(result: Result<T, E>, fallback: T): T {
        return result.ok ? result.value : fallback;
    },
} as const;
```

## Zod-validated config — types inferred from the schema

```typescript
import { z } from "zod";

export const AppConfigSchema = z.object({
    env: z.enum(["development", "staging", "production"]).default("development"),
    logLevel: z.enum(["debug", "info", "warn", "error"]).default("info"),
    database: z.object({
        host: z.string().min(1),
        port: z.number().int().min(1).max(65535).default(5432),
        name: z.string().min(1),
    }),
});

export type AppConfig = z.infer<typeof AppConfigSchema>;

export function loadConfig(env: NodeJS.ProcessEnv): AppConfig {
    const parsed = AppConfigSchema.safeParse({
        env: env.NODE_ENV,
        logLevel: env.LOG_LEVEL,
        database: {
            host: env.DB_HOST,
            port: env.DB_PORT !== undefined ? Number(env.DB_PORT) : undefined,
            name: env.DB_NAME,
        },
    });
    if (!parsed.success) {
        throw new Error(`Invalid config: ${parsed.error.message}`);
    }
    return parsed.data;
}
```

## Error hierarchy with structured context

```typescript
export class AppError extends Error {
    readonly context: Readonly<Record<string, unknown>>;
    readonly timestamp: Date;

    constructor(message: string, context: Record<string, unknown> = {}) {
        super(message);
        this.name = new.target.name;
        this.context = Object.freeze({ ...context });
        this.timestamp = new Date();
    }
}

export class NotFoundError extends AppError {
    constructor(resourceType: string, resourceId: string) {
        super(`${resourceType} with id "${resourceId}" not found`, {
            resourceType,
            resourceId,
        });
    }
}
```

## `as const` object — the canonical replacement for `enum`

```typescript
export const TaskStatus = {
    Pending: "pending",
    Running: "running",
    Succeeded: "succeeded",
    Failed: "failed",
} as const;

export type TaskStatus = (typeof TaskStatus)[keyof typeof TaskStatus];

export function isTerminal(status: TaskStatus): boolean {
    return status === TaskStatus.Succeeded || status === TaskStatus.Failed;
}
```

## Assertion function — narrow-with-throw

```typescript
export function assertDefined<T>(
    value: T | undefined,
    message: string,
): asserts value is T {
    if (value === undefined) {
        throw new Error(message);
    }
}

function consumeConfig(config: AppConfig | undefined): string {
    assertDefined(config, "config not loaded");
    // `config` is narrowed to `AppConfig` from this point.
    return config.database.host;
}
```

## `satisfies` operator — validate without widening

```typescript
type EventName = `${string}.${string}`;

export const events = {
    userCreated: "user.created",
    userDeleted: "user.deleted",
    orderPlaced: "order.placed",
} as const satisfies Record<string, EventName>;

// `events.userCreated` is the literal "user.created", not just `string`.
// The `satisfies` clause rejects a value like "userCreated" (no dot) at compile
// time, while `as Record<string, EventName>` would have widened the values.
```

## Template literal types — typed routes

```typescript
type HTTPMethod = "GET" | "POST" | "PUT" | "DELETE";
type Path = `/${string}`;
export type Endpoint = `${HTTPMethod} ${Path}`;

declare function registerRoute(endpoint: Endpoint): void;

registerRoute("GET /users");          // OK
registerRoute("POST /orders/123");    // OK
// registerRoute("get /users");       // rejected: lowercase method
// registerRoute("GET users");        // rejected: missing leading slash
```

## Const type parameter — preserve literals through generics

```typescript
export function asTuple<const T extends readonly unknown[]>(values: T): T {
    return values;
}

const STATUSES = asTuple(["draft", "published", "archived"]);
// `STATUSES` is `readonly ["draft", "published", "archived"]`,
// not `string[]` — the literal types survive the call.

export type Status = (typeof STATUSES)[number];
// "draft" | "published" | "archived"
```

## `using` declaration — automatic resource disposal

Use `using` instead of `try/finally` for any resource that implements
`[Symbol.dispose]()`. For async teardown use `await using` with
`[Symbol.asyncDispose]()`.

Compiler/runtime note: projects whose selected `lib` does not include
`Disposable`, `AsyncDisposable`, `Symbol.dispose`, and `Symbol.asyncDispose`
must add `esnext.disposable` or `esnext`. Runtimes that do not implement those
symbols need polyfills.

```typescript
class DatabaseConnection implements Disposable {
    private readonly url: string;

    constructor(connectionString: string) {
        this.url = connectionString;
    }

    query(sql: string): string {
        return `result of: ${sql}`;
    }

    [Symbol.dispose](): void {
        // flush / close the connection
    }
}

// No try/finally required — dispose is called on scope exit, even on throw.
function runQuery(connectionString: string): string {
    using conn = new DatabaseConnection(connectionString);
    return conn.query("SELECT 1");
}

// AsyncDisposable variant.
class StreamReader implements AsyncDisposable {
    constructor(readonly url: string) {}

    async [Symbol.asyncDispose](): Promise<void> {
        await Promise.resolve(); // flush and close
    }
}

async function readStream(url: string): Promise<void> {
    await using stream = new StreamReader(url);
    // stream[Symbol.asyncDispose]() is called automatically on scope exit.
}
```

## `infer T extends` — bounded inference in conditional types

Use `infer T extends SomeType` to infer and constrain in one clause,
eliminating a nested `T extends SomeType ?` guard.

```typescript
// Legacy: two nested conditions required.
type HeadLegacy<TTuple extends readonly unknown[]> =
    TTuple extends readonly [infer TFirst, ...unknown[]]
        ? TFirst extends string
            ? TFirst
            : never
        : never;

// Modern (TS 4.7+): single condition with infer-extends.
type Head<TTuple extends readonly string[]> =
    TTuple extends readonly [infer TFirst extends string, ...string[]]
        ? TFirst
        : never;

// Extract the leading segment of a dot-separated path literal.
type FirstSegment<TPath extends string> =
    TPath extends `${infer THead extends string}.${string}`
        ? THead
        : TPath;

type A = FirstSegment<"user.profile.name">; // "user"
type B = FirstSegment<"root">;              // "root"
```

## Inferred type predicate — let TypeScript narrow for you

In the TS 6.0 baseline, the compiler infers `x is T` for functions whose body
is a narrowing expression. Write the function unannotated first; add an
explicit `x is T` only at export boundaries where the predicate signature must
be stable.

```typescript
// No explicit `x is string` annotation needed.
function isString(value: unknown) {
    return typeof value === "string";
}

const mixed: (string | number | null)[] = ["a", 1, null, "b", 2];
const strings = mixed.filter(isString);
// Inferred: string[] — not (string | number | null)[]

// Explicit annotation required at a public export boundary so the
// predicate type is part of the contract and does not drift.
export class AppError extends Error {
    readonly context: Readonly<Record<string, unknown>>;

    constructor(message: string, context: Record<string, unknown> = {}) {
        super(message);
        this.name = new.target.name;
        this.context = Object.freeze({ ...context });
    }
}

export function isAppError(value: unknown): value is AppError {
    return value instanceof AppError;
}

const candidates: unknown[] = [new AppError("fail", { code: 42 }), "oops"];
const appErrors = candidates.filter(isAppError);
// Inferred: AppError[] — because isAppError has an explicit exported predicate.
```
