"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { phases, type PhaseStatus } from "@/data/phases";
import { keys, read, write, type PhaseState } from "@/lib/storage";

type ConsoleContext = {
  ready: boolean;
  get: (id: string) => PhaseState;
  setStatus: (id: string, status: PhaseStatus) => void;
  toggle: (id: string, item: string) => void;
};

const blank: PhaseState = { status: "Not Started", completed: [] };
const Context = createContext<ConsoleContext | null>(null);

export function ConsoleProvider({ children }: { children: React.ReactNode }) {
  const [states, setStates] = useState<Record<string, PhaseState>>({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setStates(Object.fromEntries(phases.map((phase) => [phase.id, read(keys.phase(phase.id), blank)])));
    setReady(true);
  }, []);

  const get = (id: string) => states[id] ?? blank;
  const save = (id: string, value: PhaseState) => {
    setStates((current) => ({ ...current, [id]: value }));
    write(keys.phase(id), value);
  };

  const value: ConsoleContext = {
    ready,
    get,
    setStatus: (id, status) => save(id, { ...get(id), status }),
    toggle: (id, item) => {
      const state = get(id);
      const completed = state.completed.includes(item)
        ? state.completed.filter((entry) => entry !== item)
        : [...state.completed, item];
      save(id, { ...state, completed });
    },
  };

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useConsole() {
  const value = useContext(Context);
  if (!value) throw new Error("ConsoleProvider is missing");
  return value;
}
