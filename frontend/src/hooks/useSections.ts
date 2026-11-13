'use client';

export interface ReportSection {
  id: number;
  report_id: string;
  order: number;
  section_type: string;
  title: string | null;
  content: string;
  visible: boolean;
  created_at: string;
  updated_at: string;
}

export interface SectionCreateInput {
  after_order: number;
  title: string | null;
  content: string;
  section_type: string;
}

export interface SectionUpdateInput {
  title?: string;
  content?: string;
  visible?: boolean;
}

function getApiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
}

function getAuthHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

async function parseJsonOrThrow(res: Response) {
  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail ?? body);
    } catch {
      // Response wasn't JSON (e.g. a network-level error page) — fall back to status only.
    }
    throw new Error(detail ? `Request failed (${res.status}): ${detail}` : `Request failed (${res.status})`);
  }
  return res.json();
}

export function useSections() {
  const fetchSections = async (reportId: string): Promise<ReportSection[]> => {
    const res = await fetch(`${getApiBase()}/api/reports/${reportId}/sections`, {
      headers: getAuthHeaders(),
    });
    return parseJsonOrThrow(res);
  };

  const parseReport = async (reportId: string): Promise<ReportSection[]> => {
    const res = await fetch(`${getApiBase()}/api/reports/${reportId}/sections/parse`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    return parseJsonOrThrow(res);
  };

  const createSection = async (reportId: string, data: SectionCreateInput): Promise<ReportSection> => {
    const res = await fetch(`${getApiBase()}/api/reports/${reportId}/sections`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return parseJsonOrThrow(res);
  };

  const updateSection = async (
    reportId: string,
    sectionId: number,
    data: SectionUpdateInput
  ): Promise<ReportSection> => {
    const res = await fetch(`${getApiBase()}/api/reports/${reportId}/sections/${sectionId}`, {
      method: 'PUT',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return parseJsonOrThrow(res);
  };

  const deleteSection = async (reportId: string, sectionId: number): Promise<void> => {
    const res = await fetch(`${getApiBase()}/api/reports/${reportId}/sections/${sectionId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    await parseJsonOrThrow(res);
  };

  const reorderSections = async (reportId: string, sectionIds: number[]): Promise<ReportSection[]> => {
    const res = await fetch(`${getApiBase()}/api/reports/${reportId}/sections/reorder`, {
      method: 'PUT',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_ids: sectionIds }),
    });
    return parseJsonOrThrow(res);
  };

  const getFinalizedContent = async (reportId: string): Promise<string> => {
    const res = await fetch(`${getApiBase()}/api/reports/${reportId}/sections/finalized`, {
      headers: getAuthHeaders(),
    });
    const data = await parseJsonOrThrow(res);
    return data.content as string;
  };

  return {
    fetchSections,
    parseReport,
    createSection,
    updateSection,
    deleteSection,
    reorderSections,
    getFinalizedContent,
  };
}
