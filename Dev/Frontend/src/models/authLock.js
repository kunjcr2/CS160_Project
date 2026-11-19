// All operations that rotate/change the HttpOnly cookie use the same lock.
// Web Locks are shared by same-origin tabs; access tokens stay in memory.
export async function withAuthLock(operation) {
  const locks = globalThis.navigator?.locks;
  if (!locks) {
    // Node unit tests have no cookie jar or other browser tabs.
    if (typeof window === "undefined") return operation();
    throw new Error(
      "Secure sign-in is unavailable in this browser. Open the app over HTTPS (or localhost) in a current browser.",
    );
  }
  const waiting = AbortSignal.timeout(30000);
  try {
    return await locks.request(
      "cs160-auth-cookie",
      { mode: "exclusive", signal: waiting },
      operation,
    );
  } catch (error) {
    if (error === waiting.reason)
      throw new Error(
        "Another tab is updating your session. Please try again shortly.",
      );
    throw error;
  }
}
