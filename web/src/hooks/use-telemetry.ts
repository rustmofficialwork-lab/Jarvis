import { useEffect, useState } from "react";
import {
  BRIDGE_URL,
  POLL_MS,
  telemetrySchema,
  type Telemetry,
} from "@/lib/telemetry";

type Battery = EventTarget & { level: number; charging: boolean };

export function useTelemetry() {
  const [battery, setBattery] = useState<{
    percent: number;
    charging: boolean;
  } | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [data, setData] = useState<Telemetry | null>(null);
  const [status, setStatus] = useState<
    "offline" | "connecting" | "live" | "unavailable"
  >("offline");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    let disposed = false;
    let source: Battery | undefined;

    const update = () => {
      if (
        !disposed &&
        source &&
        Number.isFinite(source.level) &&
        source.level >= 0 &&
        source.level <= 1
      ) {
        setBattery({
          percent: source.level * 100,
          charging: source.charging,
        });
      }
    };

    const nav = navigator as Navigator & {
      getBattery?: () => Promise<Battery>;
    };

    void nav
      .getBattery?.()
      .then((value) => {
        if (disposed) return;
        source = value;
        update();
        source.addEventListener("levelchange", update);
        source.addEventListener("chargingchange", update);
      })
      .catch(() => {});

    return () => {
      disposed = true;
      source?.removeEventListener("levelchange", update);
      source?.removeEventListener("chargingchange", update);
    };
  }, []);

  useEffect(() => {
    if (!enabled) {
      setData(null);
      setStatus("offline");
      setUpdatedAt(null);
      return;
    }

    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;

    const poll = async () => {
      controller = new AbortController();
      const timeout = setTimeout(() => controller?.abort(), 8000);

      try {
        const response = await fetch(BRIDGE_URL, {
          signal: controller.signal,
          cache: "no-store",
          credentials: "omit",
        });
        if (!response.ok) throw new Error("Laptop helper unavailable");

        const parsed = telemetrySchema.parse(await response.json());
        if (!disposed) {
          setData(parsed);
          setStatus("live");
          setUpdatedAt(new Date());
        }
      } catch {
        if (!disposed) {
          setData(null);
          setStatus("unavailable");
          setUpdatedAt(null);
        }
      } finally {
        clearTimeout(timeout);
        if (!disposed) timer = setTimeout(poll, POLL_MS);
      }
    };

    setStatus("connecting");
    void poll();

    return () => {
      disposed = true;
      clearTimeout(timer);
      controller?.abort();
    };
  }, [enabled]);

  return {
    data,
    status,
    enabled,
    setEnabled,
    updatedAt,
    batteryPercent: data?.batteryPercent ?? battery?.percent ?? null,
    charging: data?.charging ?? battery?.charging ?? null,
  };
}
