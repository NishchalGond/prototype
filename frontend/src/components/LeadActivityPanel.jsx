import { useCallback, useEffect, useState } from 'react';
import { Phone, MessageSquare, Mail, Users, StickyNote, ArrowRightLeft, Clock } from 'lucide-react';
import { apiFetch } from '../lib/api';

/**
 * Outreach for one record: what was done, and what happens next.
 *
 * Lives inside the Record Inspector rather than on a page of its own, because
 * the decision to call someone is made while looking at them. A separate
 * screen would mean finding the person twice.
 */

const KINDS = [
  { value: 'CALL', label: 'Call', Icon: Phone },
  { value: 'WHATSAPP', label: 'WhatsApp', Icon: MessageSquare },
  { value: 'EMAIL', label: 'Email', Icon: Mail },
  { value: 'MEETING', label: 'Meeting', Icon: Users },
  { value: 'NOTE', label: 'Note', Icon: StickyNote },
];

const STAGES = ['NEW', 'CONTACTED', 'INTERESTED', 'NEGOTIATING', 'WON', 'LOST', 'DO_NOT_CONTACT'];

// What the call proved about the DATA, as distinct from the sale. One click,
// because a verdict typed into a free-text box is a verdict nothing can act on.
// The three marked `suppresses` drop the record out of the list and exports;
// "No answer" deliberately does not, since nobody picking up is not evidence
// the number is wrong.
const VERDICTS = [
  { value: 'REACHED', label: 'Reached them', suppresses: false },
  { value: 'WRONG_NUMBER', label: 'Wrong number', suppresses: true },
  { value: 'NOT_OWNER', label: 'Not the owner', suppresses: true },
  { value: 'SOLD', label: 'Already sold', suppresses: true },
  { value: 'UNREACHABLE', label: 'No answer', suppresses: false },
];

// Muted, deliberately: the stage is context while reading a record, not the
// loudest thing on screen. DO_NOT_CONTACT is the exception and reads as a stop.
const STAGE_STYLE = {
  NEW: 'text-slate-600',
  CONTACTED: 'text-blue-700',
  INTERESTED: 'text-emerald-700',
  NEGOTIATING: 'text-amber-700',
  WON: 'text-emerald-800',
  LOST: 'text-slate-500',
  DO_NOT_CONTACT: 'text-rose-700',
};

const ICON_FOR = Object.fromEntries(KINDS.map((k) => [k.value, k.Icon]));

function when(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

export default function LeadActivityPanel({ recordId }) {
  const [history, setHistory] = useState([]);
  const [lead, setLead] = useState(null);
  const [kind, setKind] = useState('CALL');
  const [outcome, setOutcome] = useState('');
  const [note, setNote] = useState('');
  const [stage, setStage] = useState('');
  const [verdict, setVerdict] = useState('');
  const [nextAction, setNextAction] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await apiFetch(`/api/records/${recordId}/activity`);
      setHistory(res.ok ? await res.json() : []);
    } catch {
      // A record with no outreach yet is the normal case, not an error state.
      setHistory([]);
    }
    try {
      // A standing verdict has to be visible on open, not only after logging
      // something -- otherwise a suppressed record looks untouched.
      const res = await apiFetch(`/api/leads?record_id=${recordId}`);
      if (res.ok) {
        const rows = await res.json();
        setLead(rows.find((l) => l.record_id === recordId) || null);
      }
    } catch { /* no lead yet is the normal case */ }
  }, [recordId]);

  useEffect(() => { load(); }, [load]);

  async function logActivity(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/records/${recordId}/activity`, {
        method: 'POST',
        body: JSON.stringify({
          kind,
          outcome: outcome || null,
          note: note || null,
          stage: stage || null,
          verdict: verdict || null,
          // datetime-local has no timezone; the API stores UTC.
          next_action_at: nextAction ? new Date(nextAction).toISOString() : null,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Could not save the activity.');
      }
      setLead(await res.json());
      setOutcome(''); setNote(''); setStage(''); setNextAction(''); setVerdict('');
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function clearVerdict() {
    if (!lead) return;
    setError(null);
    try {
      const res = await apiFetch(`/api/leads/${lead.id}/verdict`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Could not clear the verdict.');
      setLead(await res.json());
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const currentStage = lead?.stage;

  return (
    <div className="p-3 rounded-xl bg-[#eef0f4] border border-slate-300/80 shadow-[inset_2px_2px_4px_#cbd2dc] space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-slate-500 font-bold">OUTREACH</span>
        <span className="flex items-center gap-2">
          {lead?.contact_verdict && (
            <span className="flex items-center gap-1.5">
              <span
                className="text-[10px] font-mono font-bold text-rose-700"
                title={`Judged by ${lead.contact_verdict_by || 'unknown'}`
                  + (lead.contact_verdict_at ? ` on ${when(lead.contact_verdict_at)}` : '')}
              >
                {lead.contact_verdict.replace(/_/g, ' ')}
              </span>
              {/* People mis-click, and a verdict hides the record from the
                  whole desk. Without a way back, nobody dares use it. */}
              <button
                type="button"
                onClick={clearVerdict}
                className="neumorph-button px-1.5 py-0.5 text-[10px] font-bold text-slate-600"
                title="Put this record back in front of the desk"
              >
                Undo
              </button>
            </span>
          )}
          {currentStage && (
            <span className={`text-[10px] font-mono font-bold ${STAGE_STYLE[currentStage] || 'text-slate-600'}`}>
              {currentStage.replace(/_/g, ' ')}
            </span>
          )}
        </span>
      </div>

      {/* Log it and move it on in one submit. Two steps to record one phone
          call is how outreach data stops getting entered. */}
      <form onSubmit={logActivity} className="space-y-2">
        <div className="flex flex-wrap gap-1.5">
          {KINDS.map(({ value, label, Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => setKind(value)}
              aria-pressed={kind === value}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-bold flex items-center space-x-1 ${
                kind === value
                  ? 'neumorph-button-primary'
                  : 'neumorph-button text-slate-600'
              }`}
            >
              <Icon className="w-3 h-3" aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <input
            type="text"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
            placeholder="Outcome (no answer, interested…)"
            aria-label="Outcome"
            className="neumorph-inset text-slate-800 rounded-lg px-2 py-1.5 text-xs focus:outline-none"
          />
          <select
            value={stage}
            onChange={(e) => setStage(e.target.value)}
            aria-label="Move to stage"
            className="neumorph-inset text-slate-800 rounded-lg px-2 py-1.5 text-xs focus:outline-none"
          >
            <option value="">Keep current stage</option>
            {STAGES.map((s) => (
              <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>

        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
          placeholder="What was said"
          aria-label="Note"
          className="neumorph-inset text-slate-800 rounded-lg px-2 py-1.5 text-xs w-full focus:outline-none resize-none"
        />

        <div className="space-y-1">
          <span className="text-[10px] font-mono text-slate-500 font-bold">
            WHAT IT PROVED ABOUT THE DATA
          </span>
          <div className="flex flex-wrap gap-1.5">
            {VERDICTS.map((v) => (
              <button
                key={v.value}
                type="button"
                onClick={() => setVerdict(verdict === v.value ? '' : v.value)}
                aria-pressed={verdict === v.value}
                title={v.suppresses
                  ? 'Removes this record from the list and exports'
                  : 'Keeps the record in the list'}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold ${
                  verdict === v.value
                    ? (v.suppresses ? 'neumorph-button text-rose-700 ring-1 ring-rose-300'
                                    : 'neumorph-button-primary')
                    : 'neumorph-button text-slate-600'
                }`}
              >
                {v.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[10px] font-mono text-slate-500 font-bold whitespace-nowrap"
                 htmlFor={`next-action-${recordId}`}>
            NEXT ACTION
          </label>
          <input
            id={`next-action-${recordId}`}
            type="datetime-local"
            value={nextAction}
            onChange={(e) => setNextAction(e.target.value)}
            className="neumorph-inset text-slate-800 rounded-lg px-2 py-1.5 text-xs flex-1 focus:outline-none"
          />
          <button
            type="submit"
            disabled={saving}
            className="neumorph-button-primary px-4 py-1.5 text-xs font-bold disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Log'}
          </button>
        </div>

        {error && (
          <p role="alert" className="text-[11px] font-bold text-rose-700">{error}</p>
        )}
      </form>

      {history.length > 0 && (
        <ul className="space-y-1.5 max-h-44 overflow-y-auto pt-1 border-t border-slate-300/80">
          {history.map((a) => {
            const Icon = ICON_FOR[a.kind] || ArrowRightLeft;
            return (
              <li key={a.id} className="flex items-start gap-2 text-xs">
                <Icon className="w-3 h-3 mt-0.5 text-slate-500 shrink-0" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <span className="font-bold text-slate-800">
                    {a.outcome || a.kind.replace(/_/g, ' ').toLowerCase()}
                  </span>
                  {a.note && <span className="text-slate-600"> — {a.note}</span>}
                  <div className="text-[10px] font-mono text-slate-500 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" aria-hidden="true" />
                    {when(a.occurred_at)} · {a.user_email}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
