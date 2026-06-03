"use client";

/**
 * Header auth controls for Clerk mode: an organization switcher (the backend requires an active
 * org) plus the user button when signed in. Renders nothing when Clerk is disabled (dev mode), so
 * it is safe to drop into any existing header without further gating.
 */
import {
  OrganizationSwitcher,
  SignedIn,
  SignedOut,
  SignInButton,
  UserButton,
} from "@clerk/nextjs";

import { CLERK_ENABLED } from "@/lib/auth-config";

export function AuthControls() {
  if (!CLERK_ENABLED) return null;
  return (
    <div className="flex items-center gap-3">
      <SignedIn>
        <OrganizationSwitcher hidePersonal afterSelectOrganizationUrl="/" />
        <UserButton />
      </SignedIn>
      <SignedOut>
        <SignInButton mode="redirect" />
      </SignedOut>
    </div>
  );
}
