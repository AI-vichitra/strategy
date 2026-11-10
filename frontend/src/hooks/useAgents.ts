'use client';
import { useCallback, useEffect, useState } from 'react';

export interface AgentQuestion {
  id: string;
  text: string;
}

export interface Agent {
  id: string;
  title: string;
  category: string;
  description: string;
  connectors: string[];
  questions: AgentQuestion[];
  enabled: boolean;
}

export interface AgentCategory {
  id: string;
  name: string;
  group?: string;
}

interface AgentsResponse {
  categories: AgentCategory[];
  agents: Agent[];
}

const EMPTY: AgentsResponse = { categories: [], agents: [] };

// Module-level cache shared by every useAgents() call, so TemplateGrid,
// AgentsPanel, and MainContent's home grid all fetch /api/agents exactly once.
let cachedData: AgentsResponse | null = null;
let inFlight: Promise<AgentsResponse> | null = null;
const subscribers = new Set<() => void>();

function notify() {
  subscribers.forEach((cb) => cb());
}

async function fetchAgents(): Promise<AgentsResponse> {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
  const res = await fetch(`${apiBase}/api/agents`);
  if (!res.ok) {
    throw new Error(`Failed to load agent catalog (${res.status})`);
  }
  const data = await res.json();
  return {
    categories: Array.isArray(data?.categories) ? data.categories : [],
    agents: Array.isArray(data?.agents) ? data.agents : [],
  };
}

function loadAgents(force = false): Promise<AgentsResponse> {
  if (force) {
    cachedData = null;
    inFlight = null;
  }
  if (cachedData) return Promise.resolve(cachedData);
  if (!inFlight) {
    inFlight = fetchAgents()
      .then((data) => {
        cachedData = data;
        inFlight = null;
        notify();
        return data;
      })
      .catch((err) => {
        inFlight = null;
        throw err;
      });
  }
  return inFlight;
}

export interface UseAgentsResult {
  agents: Agent[];
  categories: AgentCategory[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useAgents(): UseAgentsResult {
  const [data, setData] = useState<AgentsResponse>(cachedData ?? EMPTY);
  const [loading, setLoading] = useState<boolean>(!cachedData);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback((force = false) => {
    setLoading(true);
    setError(null);
    loadAgents(force)
      .then((result) => {
        setData(result);
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load agent catalog');
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    const onUpdate = () => {
      if (cachedData) {
        setData(cachedData);
        setLoading(false);
        setError(null);
      }
    };
    subscribers.add(onUpdate);

    // Initial state already captured `cachedData` via the useState initializer
    // above, so only kick off a fetch here when nothing has been cached yet.
    if (!cachedData) {
      run();
    }

    return () => {
      subscribers.delete(onUpdate);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refetch = useCallback(() => run(true), [run]);

  return {
    agents: data.agents,
    categories: data.categories,
    loading,
    error,
    refetch,
  };
}
