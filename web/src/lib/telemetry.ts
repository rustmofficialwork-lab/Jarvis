import { z } from "zod";

const percent = z.number().finite().min(0).max(100).nullable();
const bytes = z.number().finite().nonnegative().nullable();
const temperature = z.number().finite().min(-50).max(150).nullable();

export const telemetrySchema = z.object({
  version: z.literal(1),
  batteryPercent: percent,
  charging: z.boolean().nullable(),
  cpuPercent: percent,
  diskTotal: bytes,
  diskFree: bytes,
  ramTotal: bytes,
  ramFree: bytes,
  cpuTemperature: temperature,
  gpuTemperature: temperature,
  cpuName: z.string().max(300).nullable(),
  gpuName: z.string().max(300).nullable(),
  osName: z.string().max(300).nullable(),
  architecture: z.string().max(100).nullable(),
  uptimeSeconds: z.number().finite().nonnegative().nullable(),
}).refine((value) => value.diskTotal === null || value.diskFree === null || value.diskFree <= value.diskTotal,
  { message: "Free disk space exceeds capacity" })
  .refine((value) => value.ramTotal === null || value.ramFree === null || value.ramFree <= value.ramTotal,
    { message: "Free memory exceeds capacity" });

export type Telemetry = z.infer<typeof telemetrySchema>;
export const BRIDGE_URL = "http://localhost:8765/metrics";
export const POLL_MS = 3000;
export function usedPercent(total: number | null | undefined, free: number | null | undefined) {
  return total && free != null ? (1 - free / total) * 100 : null;
}
export function formatGB(value: number | null | undefined) {
  return value == null ? "Unavailable" : `${(value / 1024 ** 3).toFixed(1)} GB`;
}
export function formatPercent(value: number | null | undefined) {
  return value == null ? "—" : `${Math.round(value)}%`;
}
export function formatTemperature(value: number | null | undefined) {
  return value == null ? "Unavailable" : `${value.toFixed(1)}°C`;
}
export function formatUptime(seconds: number | null | undefined) {
  if (seconds == null) return "Unavailable";
  const s = Math.floor(seconds);
  return `${Math.floor(s / 3600)}:${String(Math.floor(s / 60) % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}