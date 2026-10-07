export const DAY_START = 480, DAY_END = 1020, OT = 30, PX = 1.7;
export const PRIORITY = ["STAT", "Urgent", "Routine"];
export const hhmm = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(Math.round(m % 60)).padStart(2, "0")}`;
