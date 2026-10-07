import { useState } from "react";
import { api } from "../api";
import type { Appointment, Resource } from "../types";

interface Props { selected?: Appointment; resources: Resource[]; role: string; onDone: () => void }

export default function EventPanel({ selected, resources, role, onDone }: Props) {
  const [msg, setMsg] = useState("");
  const canEvent = ["admin", "scheduler", "technician"].includes(role);
  const canOrder = ["admin", "scheduler", "doctor"].includes(role);
  const run = async (label: string, fn: () => Promise<unknown>) => {
    try { await fn(); setMsg(`${label}: done`); onDone(); } catch (e) { setMsg(`${label}: ${(e as Error).message}`); }
  };
  const ev = (type: string, extra: object = {}) => api("/events", "POST", { type, ...extra });
  const running = selected?.status === "in_progress";
  const sched = selected?.status === "scheduled";
  return (
    <div className="card"><h2>Inject an event</h2>
      <div className="grid2">
        <button disabled={!canEvent || !sched} onClick={() => run("Cancel", () => ev("cancellation", { appointment_id: selected!.id }))}>Cancel selected</button>
        <button disabled={!canEvent || !sched} onClick={() => run("No-show", () => ev("no_show", { appointment_id: selected!.id }))}>No-show selected</button>
        <button disabled={!canEvent || !running} onClick={() => run("Delay", () => ev("delay", { appointment_id: selected!.id, minutes: 20 }))}>Selected runs +20 min</button>
        <button disabled={!canEvent || !running} onClick={() => run("Early finish", () => ev("early_completion", { appointment_id: selected!.id }))}>Selected finished early</button>
        <button disabled={!canEvent} onClick={() => run("Machine down", () => ev("machine_down", { resource_id: resources[0]?.id, duration_min: 90 }))}>{resources[0]?.name ?? "Machine"} down 90 min</button>
        <button disabled={!canEvent} onClick={() => run("Technician out", () => ev("staff_unavailable", { technician_id: 1 }))}>Tech A leaves now</button>
        <button disabled={!canOrder} onClick={() => run("STAT MRI", () => api("/demo/stat", "POST", { test_code: "MRI_BRAIN" }))}>STAT MRI order</button>
        <button disabled={!canOrder} onClick={() => run("STAT CT", () => api("/demo/stat", "POST", { test_code: "CT_HEAD" }))}>STAT CT order</button>
      </div>
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}
