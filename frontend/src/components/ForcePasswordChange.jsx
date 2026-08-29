import { useState } from 'react';
import { KeyRound, ShieldCheck } from 'lucide-react';
import { apiFetch } from '../lib/api';

/**
 * Shown when someone signs in on a password an administrator issued.
 *
 * The API refuses every route except this one until the password is replaced,
 * so without this screen a new account is simply stuck. That is deliberate on
 * the server side -- a starting password is known to whoever typed it, and the
 * window where two people can sign in as one should last a single login.
 */
export default function ForcePasswordChange({ user, onChanged, onLogout }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    // Checked here only to save a round trip; the API validates properly.
    if (next !== confirm) {
      setError('The two new passwords do not match.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch('/api/auth/password', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || 'Could not set the password.');
      onChanged(body);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-[var(--bg-main)] p-4">
      <div className="neumorph-card w-full max-w-md rounded-3xl p-7 space-y-5">
        <div className="space-y-1.5">
          <span className="text-[10px] font-mono text-blue-600 font-bold uppercase flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" />
            First sign-in
          </span>
          <h1 className="text-xl font-black text-slate-900">Set your own password</h1>
          <p className="text-xs text-slate-500">
            {user?.full_name ? `${user.full_name}, the` : 'The'} password you were
            given is a starting one and is known to whoever set up your account.
            Choose your own before continuing — nobody, including an
            administrator, can see it.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <label className="block">
            <span className="text-[10px] font-mono text-slate-500 font-bold">
              PASSWORD YOU WERE GIVEN
            </span>
            <input
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
              autoComplete="current-password"
              className="neumorph-inset text-slate-800 rounded-lg px-3 py-2 mt-1 w-full text-sm focus:outline-none"
            />
          </label>

          <label className="block">
            <span className="text-[10px] font-mono text-slate-500 font-bold">
              NEW PASSWORD
            </span>
            <input
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              required
              minLength={10}
              autoComplete="new-password"
              className="neumorph-inset text-slate-800 rounded-lg px-3 py-2 mt-1 w-full text-sm focus:outline-none"
            />
            <span className="text-[10px] text-slate-500">At least 10 characters.</span>
          </label>

          <label className="block">
            <span className="text-[10px] font-mono text-slate-500 font-bold">
              CONFIRM NEW PASSWORD
            </span>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              autoComplete="new-password"
              className="neumorph-inset text-slate-800 rounded-lg px-3 py-2 mt-1 w-full text-sm focus:outline-none"
            />
          </label>

          {error && (
            <p role="alert" className="text-xs font-bold text-rose-700">{error}</p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="neumorph-button-primary w-full py-2.5 text-sm font-bold flex items-center justify-center gap-2 disabled:opacity-60"
          >
            <KeyRound className="w-4 h-4" aria-hidden="true" />
            {saving ? 'Saving…' : 'Set password and continue'}
          </button>
        </form>

        {/* Signing out has to stay reachable: someone who cannot remember the
            password they were given needs a way off this screen. */}
        <button
          onClick={onLogout}
          className="w-full text-[11px] font-bold text-slate-500 hover:text-slate-700"
        >
          Sign out instead
        </button>
      </div>
    </div>
  );
}
