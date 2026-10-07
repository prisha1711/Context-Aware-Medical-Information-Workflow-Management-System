import { useState } from "react";
import { api } from "../api";
import type { Appointment, EventRow, Explanation, Gap, Run, WaitItem } from "../types";
import { PRIORITY, hhmm } from "../util";

export function Waitlist({ items }: { items: WaitItem[] }) {
  return (
    <div className="card">
      <h2>Waitlist, ranked for recovery</h2>
      {items.length === 0 ? <p className="muted">Waitlist is empty.</p> : (
        <table><thead><tr><th>#</th><th>Test</th><th>Tier</th><th>Wait</th><th>Disp.</th><th>No-show</th></tr></thead>
          <tbody>{items.slice(0, 10).map((w) => (
            <tr key={w.order_id}><td>{w.order_id}</td><td>{w.test_code}</td><td>{PRIORITY[w.priority]}</td><td>{w.wait_days} d</td><td>{w.displaced}</td><td>{Math.round(w.no_show_prob * 100)}%</td></tr>
          ))}</tbody></table>
      )}
      <p className="muted">Rank: priority tier, then waiting days plus displacement credit, then lower no-show risk. No-show risk never denies access; it only orders candidates.</p>
    </div>
  );
}

export function Capacity({ gaps }: { gaps: Gap[] }) {
  return (
    <div className="card"><h2>Open capacity</h2>
      {gaps.length === 0 ? <p className="muted">No gaps of 20 min or more.</p> :
        gaps.slice(0, 8).map((g, i) => (<div key={i}>{g.resource} {hhmm(g.start_min)} to {hhmm(g.end_min)} ({g.minutes} min)</div>))}
    </div>
  );
}

export function Inspector({ appt }: { appt?: Appointment }) {
  const [ex, setEx] = useState<{ id: number; e: Explanation } | null>(null);
  if (!appt) return <div className="card"><h2>Why did this happen?</h2><p className="muted">Select an appointment on the timeline.</p></div>;
  const load = async () => { const r = await api<{ explanation: Explanation }>(`/appointments/${appt.id}/explain`); setEx({ id: appt.id, e: r.explanation }); };
  return (
    <div className="card"><h2>Appointment #{appt.order_id}: {PRIORITY[appt.priority]} {appt.test_code}</h2>
      <p>{appt.resource} {hhmm(appt.start_min)} to {hhmm(appt.end_min)}, status {appt.status}{appt.recovered ? " (recovered from waitlist)" : ""}.</p>
      <p className="muted">Predicted mean {appt.pred_mean?.toFixed(0) ?? "?"} min, planned at p80 {appt.pred_p80?.toFixed(0) ?? "?"} min. No-show risk {appt.no_show_prob != null ? Math.round(appt.no_show_prob * 100) : "?"}%. Moved {appt.moves}x.</p>
      <button onClick={load}>Explain this slot</button>
      {ex && ex.id === appt.id && (<div className="explain"><b>{ex.e.summary}</b><ul>{ex.e.details.map((d, i) => <li key={i}>{d}</li>)}</ul></div>)}
    </div>
  );
}

export function RunLog({ runs, events }: { runs: Run[]; events: EventRow[] }) {
  return (
    <div className="card"><h2>Optimizer runs and events</h2>
      <div className="log">
        {events.slice(0, 12).map((e) => (<p key={`e${e.id}`} className="ev"><small>{hhmm(e.at_min)}</small> {e.type}{e.note ? `: ${e.note}` : ""}</p>))}
        {runs.slice(0, 12).map((r) => (
          <p key={`r${r.id}`} className="run"><small>run {r.id}</small> {r.mode} on {r.trigger || "manual"} via {r.backend} in {r.solve_ms} ms: {r.scheduled} placed, {r.moved} moved, {r.recovered} recovered</p>
        ))}
      </div>
    </div>
  );
}
