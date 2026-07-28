/**
 * The signup endpoint, in one place.
 *
 * FR-1 keeps this provider-agnostic: the forms POST form-encoded `email=` to
 * whatever `PUBLIC_SIGNUP_ENDPOINT` points at (today, Buttondown's
 * embed-subscribe URL), and an unset value degrades to an honest "Signups open
 * soon" rather than a silent failure.
 *
 * That graceful degradation has a nasty failure mode, though: if the variable
 * is missing in Vercel, every form on the site politely tells visitors signups
 * aren't open — and from the outside that looks exactly like "nobody wants to
 * subscribe". So the build says so out loud. It WARNS and never throws: a
 * missing signup endpoint must not take a deploy down, same rule as
 * scripts/check-seo.mjs.
 */

export const SIGNUP_ENDPOINT: string =
  import.meta.env.PUBLIC_SIGNUP_ENDPOINT ?? "";

export const SIGNUP_LIVE = SIGNUP_ENDPOINT !== "";

if (!SIGNUP_LIVE && !(globalThis as any).__signupWarned) {
  (globalThis as any).__signupWarned = true;
  console.warn(
    "\n  [signup] PUBLIC_SIGNUP_ENDPOINT is not set — every form on this " +
      "build will\n           answer \"Signups open soon\" and nobody can " +
      "subscribe. Set it in\n           the Vercel project environment " +
      "(see landing/README.md).\n",
  );
}
