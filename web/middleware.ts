import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import { CLERK_ENABLED } from "@/lib/auth-config";

// Chat (`/`) and every admin route require an authenticated session in Clerk mode; unauthenticated
// users are redirected to the hosted Account Portal by `auth.protect()`.
const isProtectedRoute = createRouteMatcher(["/", "/admin(.*)"]);

// In dev mode there is no Clerk key, so middleware is a pass-through and the app runs with zero
// Clerk configuration. `clerkMiddleware()` is only constructed when enabled.
const middleware = CLERK_ENABLED
  ? clerkMiddleware(async (auth, req) => {
      if (isProtectedRoute(req)) await auth.protect();
    })
  : () => NextResponse.next();

export default middleware;

export const config = {
  matcher: [
    // Skip Next.js internals and static files unless referenced in search params.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpg|jpeg|gif|png|svg|ico|webp|woff2?|ttf|otf|map)).*)",
    // Always run for API routes.
    "/(api|trpc)(.*)",
  ],
};
