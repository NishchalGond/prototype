/**
 * Organisation details the UI shows people.
 *
 * One place, because the domain appears on the sign-in screen and again when
 * an administrator types a colleague's address, and two copies drift.
 *
 * This is presentation only. The API does not restrict which domain an account
 * uses -- if you want that enforced, it belongs in create_user on the server,
 * not here, where anyone can edit it in the browser.
 */
export const COMPANY_DOMAIN = 'luxurypropertieshub.com';

/** Placeholder address, e.g. name@luxurypropertieshub.com */
export const EMAIL_PLACEHOLDER = `name@${COMPANY_DOMAIN}`;

/** True when an address looks like a company one. Used for a soft hint only. */
export function isCompanyEmail(email) {
  return String(email || '').trim().toLowerCase().endsWith(`@${COMPANY_DOMAIN}`);
}
