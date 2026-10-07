import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import type { Bench } from "../types";

const COLS: [string, string][] = [["served", "Served"], ["avg_delay", "Avg delay (min)"], ["stat_wait", "STAT wait (min)"], ["overtime", "Overtime (min)"], ["utilization", "Utilization %"], ["recovered", "Recovered"], ["max_displaced", "Max displaced"]];

export default function Benchmarks() {
  const [b, setB] = useState<Bench | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<Bench>("/demo/benchmarks").then(setB).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="card"><h2>Baseline comparison</h2><p className="muted">{err}</p></div>;
  if (!b) return null;
  const rows = Object.values(b.strategies);
  const chart = rows.map((r) => ({ name: r.label, "Avg delay": +r.mean.avg_delay.toFixed(1), "Overtime": +r.mean.overtime.toFixed(1), "Max delay": +r.mean.max_delay.toFixed(1) }));
  return (
    <div className="card"><h2>Baseline ladder: {b.days} simulated days, {b.orders} orders/day</h2>
      <p className="muted">Solver: {rows[rows.length - 1].backend}{b.ortools ? "" : " (OR-Tools not installed: optimizer rows use the greedy stand-in)"}. Synthetic data, same random days for every strategy.</p>
      <table><thead><tr><th>Strategy</th>{COLS.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
        <tbody>{rows.map((r) => (<tr key={r.label}><td>{r.label}</td>{COLS.map(([k]) => <td key={k}>{r.mean[k].toFixed(1)} <small>±{r.sem[k].toFixed(1)}</small></td>)}</tr>))}</tbody></table>
      <div style={{ height: 260 }}><ResponsiveContainer><BarChart data={chart}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis /><Tooltip /><Legend />
        <Bar dataKey="Avg delay" fill="#5b7c99" /><Bar dataKey="Max delay" fill="#c98512" /><Bar dataKey="Overtime" fill="#0e7a6b" /></BarChart></ResponsiveContainer></div>
    </div>
  );
}
