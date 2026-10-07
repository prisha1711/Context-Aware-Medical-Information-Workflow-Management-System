import { useState } from "react";
import { login } from "../api";

export default function Login({ onDone }: { onDone: () => void }) {
  const [u, setU] = useState("scheduler");
  const [p, setP] = useState("sched123");
  const [err, setErr] = useState("");
  const submit = async () => {
    try { await login(u, p); onDone(); } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="card login">
      <h1>Diagnostic scheduling</h1>
      <p className="muted">Demo users: admin/admin123, scheduler/sched123, doctor/doc123, tech/tech123, viewer/view123</p>
      <input value={u} onChange={(e) => setU(e.target.value)} placeholder="Username" />
      <input type="password" value={p} onChange={(e) => setP(e.target.value)} placeholder="Password" onKeyDown={(e) => e.key === "Enter" && submit()} />
      <button className="primary" onClick={submit}>Sign in</button>
      {err && <p className="err">{err}</p>}
    </div>
  );
}
