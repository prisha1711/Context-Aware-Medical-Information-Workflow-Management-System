import { useCallback, useEffect, useRef, useState } from "react";
import { api, getSession, logout, openSocket } from "./api";
import Benchmarks from "./components/Benchmarks";
import EventPanel from "./components/EventPanel";
import KpiBar from "./components/Kpis";
import Login from "./components/Login";
import { Capacity, Inspector, RunLog, Waitlist } from "./components/Panels";
import Timeline from "./components/Timeline";
import type { Appointment, EventRow, Gap, Kpis, Resource, Run, WaitItem } from "./types";
import { hhmm } from "./util";

export default function App() {
  const [session, setSession] = useState(getSession());
  if (!session) return <Login onDone={() => setSession(getSession())} />;
  return <Dashboard role={session.role} user={session.username} />;
}

function Dashboard({ role, user }: { role: string; user: string }) {
  const [appts, setAppts] = useState<Appointment[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [waitlist, setWaitlist] = useState<WaitItem[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [kpis, setKpis] = useState<Kpis>({});
  const [runs, setRuns] = useState<Run[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [now, setNow] = useState(480);
  const [selected, setSelected] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState("");
  const busy = useRef(false);

  const refresh = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    try {
      const [s, r, w, g, k, ru, ev] = await Promise.all([
        api<{ now: number; appointments: Appointment[] }>("/schedule"), api<Resource[]>("/resources"), api<WaitItem[]>("/waitlist"),
        api<Gap[]>("/capacity"), api<Kpis>("/kpis"), api<Run[]>("/runs"), api<EventRow[]>("/events"),
      ]);
      setAppts(s.appointments); setNow(s.now); setResources(r); setWaitlist(w); setGaps(g); setKpis(k); setRuns(ru); setEvents(ev); setError("");
    } catch (e) { setError((e as Error).message); } finally { busy.current = false; }
  }, []);

  useEffect(() => { refresh(); const ws = openSocket(() => refresh()); return () => ws?.close(); }, [refresh]);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(async () => { try { await api("/demo/advance", "POST", { minutes: 5 }); } catch (e) { setError((e as Error).message); setPlaying(false); } }, 900);
    return () => clearInterval(id);
  }, [playing]);

  const act = async (fn: () => Promise<unknown>) => { try { await fn(); await refresh(); } catch (e) { setError((e as Error).message); } };
  const canDrive = ["admin", "scheduler"].includes(role);

  return (
    <div className="wrap">
      <header>
        <div><h1>Diagnostic slot recovery</h1><p className="muted">MRI and CT scheduling. Decision support only; clinicians decide what is ordered and how urgent it is.</p></div>
        <div className="ctl">
          <span className="clock">{hhmm(now)}</span>
          <button className="primary" disabled={!canDrive} onClick={() => setPlaying((p) => !p)}>{playing ? "Pause" : "Play"}</button>
          <button disabled={!canDrive} onClick={() => act(() => api("/demo/advance", "POST", { minutes: 15 }))}>+15 min</button>
          <button disabled={!canDrive} onClick={() => act(() => api("/schedule/optimize", "POST"))}>Re-optimize</button>
          <button disabled={!canDrive} onClick={() => { setPlaying(false); act(() => api("/demo/seed", "POST", { seed: Math.floor(Math.random() * 1000), n_orders: 64, disruptions: true })); }}>New day</button>
          <span className="muted">{user} ({role})</span><button onClick={() => { logout(); location.reload(); }}>Sign out</button>
        </div>
      </header>
      {error && <p className="err">{error}</p>}
      <KpiBar k={kpis} />
      <div className="layout">
        <div>
          <Timeline appts={appts} resources={resources} now={now} selected={selected} onSelect={setSelected} />
          <Inspector appt={appts.find((a) => a.id === selected)} />
          <Benchmarks />
        </div>
        <div>
          <EventPanel selected={appts.find((a) => a.id === selected)} resources={resources} role={role} onDone={refresh} />
          <Capacity gaps={gaps} />
          <Waitlist items={waitlist} />
          <RunLog runs={runs} events={events} />
        </div>
      </div>
    </div>
  );
}
