import type { Calibration, HistoryEntry } from "./types";

const HISTORY = "cardiolens.history.v1";
const CALIBRATION = "cardiolens.calibration.v1";

function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    return;
  }
}

export const loadHistory = () => read<HistoryEntry[]>(HISTORY, []);

export function addHistory(entry: HistoryEntry) {
  write(HISTORY, [entry, ...loadHistory()].slice(0, 30));
}

export function removeHistory(id: string) {
  write(HISTORY, loadHistory().filter((e) => e.id !== id));
}

export function clearHistory() {
  write(HISTORY, []);
}

export const loadCalibrations = () => read<Calibration[]>(CALIBRATION, []);
export const saveCalibrations = (items: Calibration[]) => write(CALIBRATION, items);
