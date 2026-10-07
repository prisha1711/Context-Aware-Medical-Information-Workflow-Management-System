import type { Appointment, Resource } from "../types";
import { DAY_END, DAY_START, OT, PRIORITY, PX, hhmm } from "../util";

interface Props { appts: Appointment[]; resources: Resource[]; now: number; selected: number | null; onSelect: (id: number) => void }

export default function Timeline({ appts, resources, now, selected, onSelect }: Props) {
  const width = (DAY_END + OT - DAY_START) * PX;
  const ticks: number[] = [];
  for (let t = DAY_START; t <= DAY_END; t += 60) ticks.push(t);
  return (
    <div className="card">
      <h2>Live schedule</h2>
      <div className="tl">
        <div className="axis" style={{ marginLeft: 64, width }}>
          {ticks.map((t) => (<i key={t} style={{ left: (t - DAY_START) * PX }}>{hhmm(t)}</i>))}
        </div>
        {resources.map((r) => (
          <div className="lane" key={r.id}>
            <b className="lane-name">{r.name}</b>
            <div className="track" style={{ width }}>
              {r.unavailable.map(([a, b], i) => (<div key={i} className="down" style={{ left: (a - DAY_START) * PX, width: (b - a) * PX }} />))}
              {appts.filter((a) => a.resource_id === r.id && ["scheduled", "in_progress", "completed", "cancelled", "no_show"].includes(a.status)).map((a) => {
                const done = a.status === "completed" && a.actual_start_min != null && a.actual_end_min != null;
                const start = done ? a.actual_start_min! : a.start_min;
                const end = done ? a.actual_end_min! : a.end_min;
                const cls = ["blk", `p${a.priority}`, a.status, a.recovered ? "recovered" : "", selected === a.id ? "sel" : ""].join(" ");
                return (
                  <button key={a.id} className={cls} onClick={() => onSelect(a.id)} title={`#${a.order_id} ${PRIORITY[a.priority]} ${a.test_code}`}
                    style={{ left: (start - DAY_START) * PX, width: Math.max(16, (end - start) * PX - 1) }}>#{a.order_id}</button>
                );
              })}
              <div className="now" style={{ left: (now - DAY_START) * PX }} />
            </div>
          </div>
        ))}
      </div>
      <div className="legend">
        <span><i className="sw p2" />Routine</span><span><i className="sw p1" />Urgent</span><span><i className="sw p0" />STAT</span>
        <span><i className="sw ring" />Recovered from waitlist</span><span><i className="sw dashed" />Cancelled / no-show</span><span>Hatched: machine unavailable</span>
      </div>
    </div>
  );
}
