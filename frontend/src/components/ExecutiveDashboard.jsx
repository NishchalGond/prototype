import { useCallback, useEffect, useState } from 'react';
import { Phone, Users, AlertTriangle, ShieldCheck } from 'lucide-react';
import { apiFetch } from '../lib/api';

/**
 * What the desk is doing, for the people accountable for it.
 *
 * Every number is a by-product of people working -- activities logged and
 * verdicts given -- so nobody maintains a report, and nobody can quietly stop
 * maintaining it either.
 */

const STAGE_ORDER = ['NEW', 'CONTACTED', 'INTERESTED', 'NEGOTIATING', 'WON', 'LOST',
                     'DO_NOT_CONTACT'];

function Tile({ label, value, sub, Icon, tone = 'text-slate-900' }) {
  return (
    <div className="neumorph-card rounded-2xl p-4 flex-1 min-w-[150px]">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-slate-500 font-bold">{label}</span>
        {Icon && <Icon className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />}
      </div>
      <div className={`text-2xl font-black ${tone}`}>{value}</div>
      {sub && <div className="text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}

export default function ExecutiveDashboard() {
  const [team, setTeam] = useState(null);
  const [pipeline, setPipeline] = useState(null);
  const [days, setDays] = useState(30);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [t, p] = await Promise.all([
        apiFetch(`/api/analytics/team?days=${days}`),
        apiFetch('/api/analytics/pipeline'),
      ]);
      if (!t.ok || !p.ok) throw new Error('Could not load analytics.');
      setTeam(await t.json());
      setPipeline(await p.json());
    } catch (err) {
      setError(err.message);
    }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-black text-slate-900">Executive View</h2>
          <p className="text-xs text-slate-500 font-medium">
            Who is calling, what they hold, and what the calls proved.
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {[7, 30, 90].map((d) => (
            <button key={d} onClick={() => setDays(d)} aria-pressed={days === d}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold ${
                      days === d ? 'neumorph-button-primary' : 'neumorph-button text-slate-600'}`}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      {error && <p role="alert" className="text-xs font-bold text-rose-700">{error}</p>}

      {pipeline && (
        <div className="flex flex-wrap gap-3">
          <Tile label="OPEN LEADS" value={pipeline.open_leads} Icon={Users} />
          <Tile label="OVERDUE ACTIONS" value={pipeline.overdue_actions}
                Icon={AlertTriangle}
                tone={pipeline.overdue_actions ? 'text-rose-700' : 'text-slate-900'}
                sub={pipeline.overdue_actions ? 'past their callback date' : 'nothing late'} />
          <Tile label="ACTIVITIES" value={team?.totals.activities ?? '—'} Icon={Phone}
                sub={`last ${days} days`} />
          {/* The number that says how much the database improved because
              someone picked up a phone. */}
          <Tile label="CONTACTS DISPROVED" value={pipeline.contacts_disproved}
                Icon={ShieldCheck} tone="text-emerald-700"
                sub="bad numbers found by calling" />
        </div>
      )}

      {team && (
        <div className="space-y-2">
          <h3 className="text-sm font-black text-slate-900">By person</h3>
          {!team.people.length && (
            <p className="text-xs text-slate-500">
              Nobody has logged outreach in this window.
            </p>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[10px] font-mono text-slate-500 text-left">
                  <th className="py-2 pr-3">PERSON</th>
                  <th className="py-2 pr-3">CALLS</th>
                  <th className="py-2 pr-3">ALL ACTIVITY</th>
                  <th className="py-2 pr-3">LEADS HELD</th>
                  <th className="py-2 pr-3">WON</th>
                  <th className="py-2 pr-3">DISPROVED</th>
                </tr>
              </thead>
              <tbody>
                {team.people.map((p) => (
                  <tr key={p.user} className="border-t border-slate-300/60">
                    <td className="py-2 pr-3 font-bold text-slate-800">{p.user}</td>
                    <td className="py-2 pr-3">{p.activities.CALL || 0}</td>
                    <td className="py-2 pr-3">{p.total_activities}</td>
                    <td className="py-2 pr-3">{p.leads_held}</td>
                    <td className="py-2 pr-3 text-emerald-700 font-bold">
                      {p.leads_by_stage.WON || 0}
                    </td>
                    {/* Deliberately shown beside the sales numbers: someone
                        returning many bad-contact verdicts is improving the
                        database, not underperforming. */}
                    <td className="py-2 pr-3 text-slate-600">
                      {['WRONG_NUMBER', 'NOT_OWNER', 'SOLD']
                        .reduce((n, v) => n + (p.verdicts_given[v] || 0), 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {pipeline && (
        <div className="space-y-2">
          <h3 className="text-sm font-black text-slate-900">Pipeline</h3>
          <div className="flex flex-wrap gap-2">
            {STAGE_ORDER.map((s) => (
              <div key={s} className="neumorph-card rounded-xl px-3 py-2">
                <div className="text-[10px] font-mono text-slate-500 font-bold">
                  {s.replace(/_/g, ' ')}
                </div>
                <div className="text-lg font-black text-slate-900">
                  {pipeline.by_stage[s] ?? 0}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
