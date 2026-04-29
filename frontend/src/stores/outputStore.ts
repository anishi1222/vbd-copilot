import { create } from "zustand";
import type { OutputFile, GroupedOutput } from "@/api/types";
import { listOutputs, listGroupedOutputs } from "@/api/client";

interface OutputStore {
  outputs: OutputFile[];
  grouped: GroupedOutput[];
  loading: boolean;
  error: string | null;
  lastFetched: number;
  categoryFilter: string;
  searchQuery: string;
  viewMode: "grid" | "list";

  fetch: () => Promise<void>;
  fetchForce: () => Promise<void>;
  setCategoryFilter: (c: string) => void;
  setSearchQuery: (q: string) => void;
  setViewMode: (m: "grid" | "list") => void;
  filtered: () => OutputFile[];
  filteredGrouped: () => GroupedOutput[];
}

export const useOutputStore = create<OutputStore>((set, get) => ({
  outputs: [],
  grouped: [],
  loading: false,
  error: null,
  lastFetched: 0,
  categoryFilter: "all",
  searchQuery: "",
  viewMode: "grid",

  fetch: async () => {
    // Skip the network round-trip if data is less than 5 s old.
    // The OutputLibrary page also subscribes to job outputFiles changes and
    // calls fetch() when new files arrive — that path bypasses this guard via
    // fetchForce() so fresh outputs always land immediately.
    const { lastFetched } = get();
    if (lastFetched > 0 && Date.now() - lastFetched < 5_000) return;

    set({ loading: true, error: null });
    try {
      const [outputs, grouped] = await Promise.all([
        listOutputs(),
        listGroupedOutputs(),
      ]);
      set({ outputs, grouped, loading: false, lastFetched: Date.now() });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },

  fetchForce: async () => {
    set({ loading: true, error: null });
    try {
      const [outputs, grouped] = await Promise.all([
        listOutputs(),
        listGroupedOutputs(),
      ]);
      set({ outputs, grouped, loading: false, lastFetched: Date.now() });
    } catch (e: any) {
      set({ error: e.message, loading: false });
    }
  },

  setCategoryFilter: (c) => set({ categoryFilter: c }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  setViewMode: (m) => set({ viewMode: m }),

  filtered: () => {
    const { outputs, categoryFilter, searchQuery } = get();
    let result = outputs;
    if (categoryFilter !== "all") {
      result = result.filter((o) => o.category === categoryFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (o) =>
          o.name.toLowerCase().includes(q) ||
          o.relative.toLowerCase().includes(q),
      );
    }
    return result;
  },

  filteredGrouped: () => {
    const { grouped, categoryFilter, searchQuery } = get();
    let result = grouped;
    if (categoryFilter !== "all") {
      result = result.filter((o) => o.category === categoryFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (o) => o.title.toLowerCase().includes(q) || o.id.toLowerCase().includes(q),
      );
    }
    return result;
  },
}));
