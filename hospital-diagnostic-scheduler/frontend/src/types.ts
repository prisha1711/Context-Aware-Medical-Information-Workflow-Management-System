export interface Appointment {
  id: number; order_id: number; patient: string; test_code: string; modality: string; priority: number;
  resource_id: number; resource: string; technician_id: number | null; start_min: number; end_min: number;
  planned_minutes: number; status: string; recovered: boolean; moves: number; source: string;
  actual_start_min: number | null; actual_end_min: number | null; wait_days: number; displaced: number;
  pred_mean: number | null; pred_p80: number | null; no_show_prob: number | null;
}
export interface Resource { id: number; name: string; modality: string; room: string; unavailable: number[][] }
export interface WaitItem { order_id: number; patient: string; test_code: string; modality: string; priority: number; wait_days: number; displaced: number; no_show_prob: number }
export interface Gap { resource: string; start_min: number; end_min: number; minutes: number }
export interface Run { id: number; mode: string; trigger: string; backend: string; status: string; solve_ms: number; scheduled: number; unscheduled: number; moved: number; recovered: number; stages: Record<string, number> }
export interface EventRow { id: number; type: string; at_min: number; note: string; payload: Record<string, unknown> }
export interface Explanation { summary: string; details: string[] }
export interface Session { token: string; role: string; username: string }
export type Kpis = Record<string, number>;
export interface BenchRow { label: string; backend: string; mean: Record<string, number>; sem: Record<string, number> }
export interface Bench { days: number; orders: number; ortools: boolean; created: string; strategies: Record<string, BenchRow> }
