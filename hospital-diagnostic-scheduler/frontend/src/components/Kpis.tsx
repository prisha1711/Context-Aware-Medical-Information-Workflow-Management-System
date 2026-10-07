import type { Kpis } from "../types";

export default function KpiBar({ k }: { k: Kpis }) {
  const items: [string, string][] = [
    ["Served", String(k.served ?? 0)], ["Scheduled", String(k.scheduled ?? 0)], ["Waitlisted", String(k.waitlisted ?? 0)],
    ["Avg day-of delay", `${k.avg_delay_min ?? 0} min`], ["STAT wait", `${k.stat_wait_min ?? 0} min`],
    ["Overtime", `${k.overtime_min ?? 0} min`], ["Utilization", `${k.utilization_pct ?? 0}%`],
    ["Slots recovered", `${k.slots_recovered ?? 0} of ${k.slots_freed ?? 0}`], ["Plan moves", String(k.plan_moves ?? 0)],
    ["Max times displaced", String(k.max_displaced ?? 0)],
  ];
  return (
    <div className="kpis">
      {items.map(([l, v]) => (<div key={l} className="kpi"><b>{v}</b><span>{l}</span></div>))}
    </div>
  );
}
