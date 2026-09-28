/**
 * The ears<->brain seam credential (CONTRACT §2). When SEAM_SHARED_SECRET is set, ears
 * refuses any handshake or store call that does not carry it; the brain sends it as one
 * header on both. Unset means an unauthenticated seam, for a laptop with both on loopback.
 */
export const SEAM_HEADER = "x-seam-secret";

export function seamHeaders(secret: string | undefined): Record<string, string> {
  return secret ? { [SEAM_HEADER]: secret } : {};
}
