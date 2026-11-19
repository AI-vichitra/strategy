'use client';
import { useCallback, useEffect, useState } from 'react';

export interface PptxTemplate {
  id: string;
  name: string;
  description: string;
}

// Module-level cache shared by every useTemplates() call, so every export
// menu instance fetches the public /api/pptx-templates catalog exactly once
// (same pattern as useAgents.ts).
let cachedTemplates: PptxTemplate[] | null = null;
let inFlight: Promise<PptxTemplate[]> | null = null;

async function fetchTemplates(): Promise<PptxTemplate[]> {
  const apiBase = process.env.NEXT_PUBLIC_API_URL;
  const res = await fetch(`${apiBase}/api/pptx-templates`);
  if (!res.ok) {
    throw new Error(`Failed to load PPTX templates (${res.status})`);
  }
  const data = await res.json();
  if (!Array.isArray(data)) return [];
  return data.map((t) => ({
    id: String(t?.id ?? ''),
    name: String(t?.name ?? t?.id ?? ''),
    description: String(t?.description ?? ''),
  }));
}

function loadTemplates(): Promise<PptxTemplate[]> {
  if (cachedTemplates) return Promise.resolve(cachedTemplates);
  if (!inFlight) {
    inFlight = fetchTemplates()
      .then((data) => {
        cachedTemplates = data;
        inFlight = null;
        return data;
      })
      .catch((err) => {
        inFlight = null;
        throw err;
      });
  }
  return inFlight;
}

export interface UseTemplatesResult {
  templates: PptxTemplate[];
  loading: boolean;
  error: string | null;
}

export function useTemplates(): UseTemplatesResult {
  const [templates, setTemplates] = useState<PptxTemplate[]>(cachedTemplates ?? []);
  const [loading, setLoading] = useState<boolean>(!cachedTemplates);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(() => {
    if (cachedTemplates) {
      setTemplates(cachedTemplates);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    loadTemplates()
      .then((data) => {
        setTemplates(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load PPTX templates');
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { templates, loading, error };
}
