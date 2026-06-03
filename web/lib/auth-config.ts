/**
 * Auth-mode switch, mirroring the backend's AUTH_PROVIDER. When `CLERK_ENABLED` is false the app
 * keeps today's behavior (x-dev-principal header, no ClerkProvider, no route protection) so local
 * dev and CI run with zero Clerk configuration.
 *
 * This is a build-time constant: `NEXT_PUBLIC_*` values are inlined by Next at build, so the value
 * is stable across renders (which lets `auth-headers.ts` pick its hook implementation at module
 * load — see the note there).
 */
const PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";

export const CLERK_ENABLED =
  process.env.NEXT_PUBLIC_AUTH_MODE !== "dev" &&
  PUBLISHABLE_KEY.length > 0 &&
  !PUBLISHABLE_KEY.includes("REPLACE_ME");
