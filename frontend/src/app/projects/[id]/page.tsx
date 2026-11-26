'use client';
import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import FileIcon from '@/components/FileIcon';
import styles from './page.module.css';
import ConfirmModal from '../../../components/ConfirmModal';
import Sidebar from '../../../components/builder/Sidebar';
import VoiceInput from '../../../components/builder/VoiceInput';

// Matches backend.schemas.brand.normalize_target_market's canonical shape.
interface TargetMarket {
  region: string | null;
  cities: string[];
  custom_region: string | null;
}

// Matches backend.schemas.brand.BRAND_BRIEF_KEYS exactly — NOT the generic
// mission/vision/values shape; normalize_brand_brief always returns all nine
// keys as strings ("" when unset, never missing).
interface BrandBrief {
  what_we_do: string;
  positioning: string;
  target_audience: string;
  differentiators: string;
  products_services: string;
  tone_of_voice: string;
  business_model: string;
  proof_points: string;
  market_context: string;
}

// Matches backend.schemas.brand.SOCIAL_PLATFORMS; normalize_social_handles
// returns only the platforms it actually found, so every key is optional.
interface SocialHandles {
  instagram?: string;
  linkedin?: string;
  x?: string;
  youtube?: string;
  facebook?: string;
  tiktok?: string;
}

interface ReferenceDocItem {
  ref_id: string;
  filename: string;
}

interface BrandDetail {
  name: string;
  website_url: string | null;
  category: string;
  region: string | null;
  target_market: TargetMarket | null;
  brand_context: string | null;
  brand_brief: BrandBrief | null;
  social_handles: SocialHandles | null;
  logo_url: string | null;
  colors: { primary?: string; secondary?: string; accent?: string } | null;
  reference_docs: ReferenceDocItem[];
}

interface CompetitorItem {
  name: string;
  website_url: string;
  logo_url?: string;
}

interface ChatItem {
  id: string;
  title: string;
  created_at: string | null;
  last_message_at: string | null;
  message_count: number;
}

interface ProjectDetails {
  brand_config_id: string;
  brand: BrandDetail;
  competitors_selected: CompetitorItem[];
  competitors_used: CompetitorItem[];
  chats: ChatItem[];
  status: string;
  created_at: string | null;
  last_updated: string | null;
}

const BRAND_BRIEF_FIELDS: { key: keyof BrandBrief; label: string }[] = [
  { key: 'what_we_do', label: 'What We Do' },
  { key: 'positioning', label: 'Positioning' },
  { key: 'target_audience', label: 'Target Audience' },
  { key: 'differentiators', label: 'Differentiators' },
  { key: 'products_services', label: 'Products & Services' },
  { key: 'tone_of_voice', label: 'Tone of Voice' },
  { key: 'business_model', label: 'Business Model' },
  { key: 'proof_points', label: 'Proof Points' },
  { key: 'market_context', label: 'Market Context' },
];

const SOCIAL_PLATFORM_ORDER: (keyof SocialHandles)[] = ['instagram', 'linkedin', 'x', 'youtube', 'facebook', 'tiktok'];
const SOCIAL_PLATFORM_LABELS: Record<keyof SocialHandles, string> = {
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
  x: 'X (Twitter)',
  youtube: 'YouTube',
  facebook: 'Facebook',
  tiktok: 'TikTok',
};

const SOCIAL_PLATFORM_ICONS: Record<keyof SocialHandles, React.ReactNode> = {
  instagram: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ borderRadius: '5px', flexShrink: 0 }}>
      <defs>
        <radialGradient id="igIconProjGrad" cx="20%" cy="105%" r="130%">
          <stop offset="0%" stopColor="#fdf497" />
          <stop offset="10%" stopColor="#fdf497" />
          <stop offset="50%" stopColor="#fd5949" />
          <stop offset="70%" stopColor="#d6249f" />
          <stop offset="100%" stopColor="#285AEB" />
        </radialGradient>
      </defs>
      <rect width="24" height="24" rx="6" fill="url(#igIconProjGrad)" />
      <rect x="5.5" y="5.5" width="13" height="13" rx="3.5" stroke="#ffffff" strokeWidth="1.6" fill="none" />
      <circle cx="12" cy="12" r="3.2" stroke="#ffffff" strokeWidth="1.6" fill="none" />
      <circle cx="15.8" cy="8.2" r="0.9" fill="#ffffff" />
    </svg>
  ),
  linkedin: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ borderRadius: '5px', flexShrink: 0 }}>
      <rect width="24" height="24" rx="5" fill="#0A66C2" />
      <circle cx="7.5" cy="7.5" r="1.5" fill="#ffffff" />
      <rect x="6" y="10" width="3" height="8" rx="0.5" fill="#ffffff" />
      <path d="M11 10h2.8v1.2c.4-.7 1.4-1.4 2.7-1.4 2.6 0 3.5 1.5 3.5 4v4.2h-3V14.3c0-1-.4-1.8-1.5-1.8s-1.5.8-1.5 1.8V18H11V10z" fill="#ffffff" />
    </svg>
  ),
  x: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ borderRadius: '5px', flexShrink: 0 }}>
      <rect width="24" height="24" rx="5" fill="#000000" />
      <path d="M15.5 5.5h2l-4.4 5 5.2 6.9h-4l-3.2-4.2-3.6 4.2h-2l4.7-5.4L5.2 5.5h4.1l2.9 3.8 3.3-3.8zm-.7 10.7h1.1L8.5 6.6H7.3l7.5 9.6z" fill="#ffffff" />
    </svg>
  ),
  youtube: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ borderRadius: '5px', flexShrink: 0 }}>
      <rect width="24" height="24" rx="5" fill="#FF0000" />
      <path d="M10 8.5l5.5 3.5-5.5 3.5V8.5z" fill="#ffffff" />
    </svg>
  ),
  facebook: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ borderRadius: '5px', flexShrink: 0 }}>
      <rect width="24" height="24" rx="5" fill="#1877F2" />
      <path d="M15.5 12.5h-2.3V20h-3.1v-7.5H8.5V9.9h1.6V8.1c0-2.2 1.3-3.6 3.5-3.6 1 0 2 .1 2.2.1v2.5h-1.3c-1.1 0-1.4.5-1.4 1.3v1.5h2.7l-.3 2.6z" fill="#ffffff" />
    </svg>
  ),
  tiktok: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" style={{ borderRadius: '5px', flexShrink: 0 }}>
      <rect width="24" height="24" rx="5" fill="#000000" />
      <path d="M15.2 6.2c.7.9 1.7 1.5 2.8 1.6v2.2c-1.1 0-2.1-.4-2.8-1.1v4.8c0 2.4-1.9 4.3-4.3 4.3S6.6 16.1 6.6 13.7s1.9-4.3 4.3-4.3c.3 0 .7 0 1 .1v2.3c-.3-.1-.6-.2-1-.2-1.2 0-2.1.9-2.1 2.1s.9 2.1 2.1 2.1 2.2-.9 2.2-2.1V5h2.1z" fill="#ffffff" />
    </svg>
  ),
};

function statusClass(status: string) {
  if (status === 'complete') return styles.statusComplete;
  if (status === 'running') return styles.statusRunning;
  if (status === 'failed') return styles.statusFailed;
  return styles.statusPending;
}

function statusLabel(status: string) {
  if (status === 'complete') return 'Complete';
  if (status === 'running') return 'Running';
  if (status === 'failed') return 'Failed';
  return 'Pending';
}

function formatDate(iso: string | null) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
}

// Short relative stamp ("2 minutes ago", "22 hours ago", "Oct 26") for
// Recents rows — the same formatting the report sidebar used previously.
function formatRelative(iso: string | null) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);
  if (diffMin < 1) return 'Just now';
  if (diffMin === 1) return '1 minute ago';
  if (diffMin < 60) return `${diffMin} minutes ago`;
  if (diffHr === 1) return '1 hour ago';
  if (diffHr < 24) return `${diffHr} hours ago`;
  if (diffDay === 1) return 'Yesterday';
  if (diffDay < 7) return `${diffDay} days ago`;
  return formatDate(iso);
}

function formatTargetMarket(tm: TargetMarket | null): string {
  if (!tm || !tm.region) return '—';
  if (tm.region === 'global') return 'Global';
  if (tm.region === 'other') return tm.custom_region || 'Other';
  const label = tm.region.charAt(0).toUpperCase() + tm.region.slice(1);
  const cities = (tm.cities || []).filter(Boolean);
  return cities.length > 0 ? `${label} — ${cities.join(', ')}` : label;
}

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

// Compact clickable row for the sidebar (replaces the old expanded/
// collapsible sections) — label left, item count + chevron right.
function SidebarRow({ label, count, onClick }: { label: string; count: string; onClick: () => void }) {
  return (
    <button type="button" className={styles.sidebarRow} onClick={onClick}>
      <span className={styles.sidebarRowLabel}>{label}</span>
      <span className={styles.sidebarRowMeta}>
        {count}
        <span className={styles.sidebarRowChevron}>›</span>
      </span>
    </button>
  );
}

export default function ProjectDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.id as string;
  const [data, setData] = useState<ProjectDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chatDraft, setChatDraft] = useState('');
  const [activeDrawer, setActiveDrawer] = useState<'instructions' | 'context' | 'social' | null>(null);
  const [drawerEditing, setDrawerEditing] = useState(false);
  const [editForm, setEditForm] = useState<Record<string, string>>({});
  const [socialRows, setSocialRows] = useState<(keyof SocialHandles)[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [docUploading, setDocUploading] = useState(false);
  const [docUploadError, setDocUploadError] = useState<string | null>(null);
  const [deletingRefId, setDeletingRefId] = useState<string | null>(null);
  const [failedLogoUrl, setFailedLogoUrl] = useState<string | null>(null);
  const [removeDocConfirm, setRemoveDocConfirm] = useState<{ isOpen: boolean; doc: ReferenceDocItem | null }>({ isOpen: false, doc: null });
  // Chat 3-dots menu
  const [chatMenuId, setChatMenuId] = useState<string | null>(null);
  const [deleteChatId, setDeleteChatId] = useState<string | null>(null);
  const [renamingChatId, setRenamingChatId] = useState<string | null>(null);
  const [chatRenameInput, setChatRenameInput] = useState('');
  const [chatRenameError, setChatRenameError] = useState('');
  const [isChatRenaming, setIsChatRenaming] = useState(false);
  // Attach files for new chat input
  const [chatAttachFiles, setChatAttachFiles] = useState<File[]>([]);
  const chatFileInputRef = useRef<HTMLInputElement>(null);
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);
  const voiceInitialTextRef = useRef('');
  const chatTextareaRef = useRef<HTMLTextAreaElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close 3-dots popover on outside click
  useEffect(() => {
    if (!chatMenuId) return;
    const handleOutsideClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setChatMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [chatMenuId]);

  const resetEditState = () => {
    setDrawerEditing(false);
    setEditForm({});
    setSocialRows([]);
    setSaveError(null);
    setDocUploadError(null);
    setDeletingRefId(null);
  };

  const openDrawer = (drawer: 'instructions' | 'context' | 'social') => {
    setActiveDrawer(drawer);
    resetEditState();
  };

  const closeDrawer = () => {
    setActiveDrawer(null);
    resetEditState();
  };

  useEffect(() => {
    if (!projectId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    const headers = authHeaders();

    fetch(`${apiBase}/api/projects/${projectId}/details`, { headers })
      .then(res => {
        if (!res.ok) throw new Error(res.status === 404 ? 'Project not found.' : `Error ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleOpenChat = (chatId: string, brandConfigId: string, draftMessage?: string) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('brand_config_id', brandConfigId);
      const trimmed = draftMessage?.trim();
      if (trimmed) {
        sessionStorage.setItem('pending_chat_message', trimmed);
      } else {
        sessionStorage.removeItem('pending_chat_message');
      }
    }
    router.push(`/build?project=${chatId}`);
  };

  const handleChatDraftChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setChatDraft(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  // Chat paste handler
  const handleChatInputPaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const { clipboardData } = e;
    if (!clipboardData) return;
    const pastedFiles: File[] = [];
    if (clipboardData.files && clipboardData.files.length > 0) {
      Array.from(clipboardData.files).forEach(f => pastedFiles.push(f));
    } else if (clipboardData.items) {
      Array.from(clipboardData.items).forEach(item => {
        if (item.kind === 'file') { const f = item.getAsFile(); if (f) pastedFiles.push(f); }
      });
    }
    if (pastedFiles.length > 0) {
      e.preventDefault();
      const renamed = pastedFiles.map(f => {
        if (f.type.startsWith('image/')) {
          const ext = f.type.split('/')[1] || 'png';
          return new File([f], `pasted-image-${Date.now()}.${ext}`, { type: f.type });
        }
        return f;
      });
      setChatAttachFiles(prev => [...prev, ...renamed]);
      return;
    }
    const text = clipboardData.getData('text/plain');
    if (text && (text.length >= 3500 || text.split('\n').length >= 45)) {
      e.preventDefault();
      const blob = new Blob([text], { type: 'text/plain' });
      const pf = new File([blob], 'Pasted content.txt', { type: 'text/plain' });
      setChatAttachFiles(prev => [...prev, pf]);
    }
  };

  // Chat 3-dots: delete
  const handleDeleteChat = async (chatId: string) => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    try {
      const res = await fetch(`${apiBase}/api/projects/${chatId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (res.ok) {
        setData(prev => prev ? { ...prev, chats: prev.chats.filter(c => c.id !== chatId) } : prev);
        window.dispatchEvent(new CustomEvent('projectDeleted', { detail: { projectId: chatId } }));
      }
    } catch (err) {
      console.error('Failed to delete chat:', err);
    }
    setChatMenuId(null);
    setDeleteChatId(null);
  };

  // Chat 3-dots: open rename
  const openChatRename = (chatId: string, currentTitle: string) => {
    setRenamingChatId(chatId);
    setChatRenameInput(currentTitle);
    setChatRenameError('');
    setChatMenuId(null);
  };

  const closeChatRename = () => {
    setRenamingChatId(null);
    setChatRenameInput('');
    setChatRenameError('');
  };

  // Chat in-place rename
  const handleSaveInplaceRename = async (chatId: string) => {
    const trimmed = chatRenameInput.trim();
    if (!trimmed) {
      closeChatRename();
      return;
    }
    const currentChat = data?.chats.find(c => c.id === chatId);
    if (currentChat && currentChat.title === trimmed) {
      closeChatRename();
      return;
    }
    setIsChatRenaming(true);
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    try {
      const res = await fetch(`${apiBase}/api/projects/${chatId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ title: trimmed }),
      });
      if (res.ok) {
        setData(prev => prev ? {
          ...prev,
          chats: prev.chats.map(c => c.id === chatId ? { ...c, title: trimmed } : c)
        } : prev);
        window.dispatchEvent(new CustomEvent('projectRenamed', {
          detail: { projectId: chatId, title: trimmed, brand_config_id },
        }));
        closeChatRename();
      }
    } catch (err) {
      console.error('Failed to rename chat:', err);
    } finally {
      setIsChatRenaming(false);
    }
  };

  if (loading) {
    return <div className={styles.loadingWrap}>Loading project details…</div>;
  }

  if (error || !data) {
    return (
      <div className={styles.errorWrap}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#D4A843" strokeWidth="1.5">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><circle cx="12" cy="16" r="1" fill="#D4A843"/>
        </svg>
        <p>{error ?? 'Project not found.'}</p>
        <Link href="/build" prefetch={false} className={styles.backLink}>← Back to projects</Link>
      </div>
    );
  }

  const { brand_config_id, brand, competitors_selected, chats, status, created_at, last_updated } = data;

  const briefFilled = BRAND_BRIEF_FIELDS.filter(f => (brand.brand_brief as BrandBrief | null)?.[f.key]?.trim());
  const hasBrief = briefFilled.length > 0;

  const socialEntries = SOCIAL_PLATFORM_ORDER
    .map(platform => ({ platform, url: brand.social_handles?.[platform] }))
    .filter((e): e is { platform: keyof SocialHandles; url: string } => !!e.url);

  const startEdit = () => {
    setSaveError(null);
    if (activeDrawer === 'instructions') {
      const briefNow = brand.brand_brief as BrandBrief | null;
      setEditForm({
        what_we_do: briefNow?.what_we_do || '',
        positioning: briefNow?.positioning || '',
        target_audience: briefNow?.target_audience || '',
        differentiators: briefNow?.differentiators || '',
        products_services: briefNow?.products_services || '',
        tone_of_voice: briefNow?.tone_of_voice || '',
        business_model: briefNow?.business_model || '',
        proof_points: briefNow?.proof_points || '',
        market_context: briefNow?.market_context || '',
      });
    } else if (activeDrawer === 'social') {
      const handlesNow = brand.social_handles || {};
      const form: Record<string, string> = {};
      const rows: (keyof SocialHandles)[] = [];
      SOCIAL_PLATFORM_ORDER.forEach(platform => {
        form[platform] = handlesNow[platform] || '';
        if (handlesNow[platform]) rows.push(platform);
      });
      setEditForm(form);
      setSocialRows(rows);
    } else if (activeDrawer === 'context') {
      setEditForm({
        website_url: brand.website_url || '',
        category: brand.category || '',
        target_market: brand.target_market?.custom_region || brand.target_market?.region || '',
      });
    }
    setDrawerEditing(true);
  };

  const cancelEdit = () => {
    setDrawerEditing(false);
    setEditForm({});
    setSocialRows([]);
    setSaveError(null);
  };

  const handleSave = async () => {
    if (!activeDrawer) return;
    setSaving(true);
    setSaveError(null);
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    const headers = { 'Content-Type': 'application/json', ...authHeaders() };
    const endpointByDrawer = {
      instructions: 'brand-brief',
      social: 'social-handles',
      context: 'brand-context',
    } as const;

    let body: Record<string, string> = editForm;
    if (activeDrawer === 'social') {
      body = {};
      SOCIAL_PLATFORM_ORDER.forEach(platform => { body[platform] = editForm[platform] || ''; });
    }

    try {
      const res = await fetch(`${apiBase}/api/projects/${projectId}/${endpointByDrawer[activeDrawer]}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => null);
        throw new Error(errBody?.detail || `Error ${res.status}`);
      }

      setData(prev => {
        if (!prev) return prev;
        const nextBrand: BrandDetail = { ...prev.brand };
        if (activeDrawer === 'instructions') {
          nextBrand.brand_brief = { ...(body as unknown as BrandBrief) };
        } else if (activeDrawer === 'social') {
          const handles: SocialHandles = {};
          SOCIAL_PLATFORM_ORDER.forEach(platform => {
            if (body[platform]) handles[platform] = body[platform];
          });
          nextBrand.social_handles = handles;
        } else if (activeDrawer === 'context') {
          nextBrand.website_url = body.website_url;
          nextBrand.category = body.category;
          nextBrand.target_market = {
            region: body.target_market.trim().toLowerCase() || null,
            cities: [],
            custom_region: null,
          };
        }
        return { ...prev, brand: nextBrand };
      });
      setDrawerEditing(false);
      setSaving(false);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save');
      setSaving(false);
    }
  };

  const MAX_REFERENCE_DOC_BYTES = 10 * 1024 * 1024;

  const handleReferenceFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    if (file.size > MAX_REFERENCE_DOC_BYTES) {
      setDocUploadError('File exceeds the 10MB size limit.');
      return;
    }

    setDocUploading(true);
    setDocUploadError(null);
    const apiBase = process.env.NEXT_PUBLIC_API_URL;

    try {
      const formData = new FormData();
      formData.append('file', file);
      const uploadRes = await fetch(`${apiBase}/api/brands/upload-reference`, {
        method: 'POST',
        headers: authHeaders(),
        body: formData,
      });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => null);
        throw new Error(err?.detail || 'Upload failed. Please try again.');
      }
      const uploaded = await uploadRes.json();

      const attachRes = await fetch(`${apiBase}/api/projects/${projectId}/reference-docs`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ ref_id: uploaded.ref_id, filename: uploaded.filename }),
      });
      if (!attachRes.ok) {
        const err = await attachRes.json().catch(() => null);
        throw new Error(err?.detail || 'Failed to save the document. Please try again.');
      }
      const attached = await attachRes.json();

      setData(prev => {
        if (!prev) return prev;
        return { ...prev, brand: { ...prev.brand, reference_docs: attached.reference_docs || [] } };
      });
      setDocUploading(false);
    } catch (err) {
      setDocUploadError(err instanceof Error ? err.message : 'Upload failed. Please try again.');
      setDocUploading(false);
    }
  };

  const handleRemoveReferenceDoc = (doc: ReferenceDocItem) => {
    setRemoveDocConfirm({ isOpen: true, doc });
  };

  const doRemoveReferenceDoc = async (doc: ReferenceDocItem) => {
    setRemoveDocConfirm({ isOpen: false, doc: null });
    setDeletingRefId(doc.ref_id);
    setDocUploadError(null);
    const apiBase = process.env.NEXT_PUBLIC_API_URL;

    try {
      const res = await fetch(`${apiBase}/api/projects/${projectId}/reference-docs/${encodeURIComponent(doc.ref_id)}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || 'Failed to remove the document. Please try again.');
      }
      const result = await res.json();

      setData(prev => {
        if (!prev) return prev;
        return { ...prev, brand: { ...prev.brand, reference_docs: result.reference_docs || [] } };
      });
      setDeletingRefId(null);
    } catch (err) {
      setDocUploadError(err instanceof Error ? err.message : 'Failed to remove the document. Please try again.');
      setDeletingRefId(null);
    }
  };

  const hasColors = !!brand.colors && !!(brand.colors.primary || brand.colors.secondary || brand.colors.accent);
  const resolveLogo = (url?: string | null) => {
    if (!url) return null;
    if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:') || url.startsWith('blob:')) {
      return url;
    }
    const base = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/+$/, '');
    const path = url.startsWith('/') ? url : `/${url}`;
    return `${base}${path}`;
  };
  const logoSrc = resolveLogo(brand.logo_url);
  const logoVisible = !!logoSrc && failedLogoUrl !== brand.logo_url;
  const contextItemCount = [
    !!brand.website_url,
    !!brand.category,
    !!brand.target_market?.region,
    hasColors,
    competitors_selected.length > 0,
  ].filter(Boolean).length;

  return (
    <div className={styles.pageShell}>
      <Sidebar />
      <main className={styles.container}>
      <div className={styles.inner}>        {/* Back */}
        <Link href="/build" prefetch={false} className={styles.backLink}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
          </svg>
          Back to projects
        </Link>

        {/* Header */}
        <div>
          <h1 className={styles.pageTitle}>{brand.name}</h1>
          <div className={styles.statusRow}>
            <span className={`${styles.statusBadge} ${statusClass(status)}`}>
              {statusLabel(status)}
            </span>
            {created_at && <span className={styles.metaDate}>Created {formatDate(created_at)}</span>}
            {last_updated && last_updated !== created_at && (
              <span className={styles.metaDate}>· Updated {formatDate(last_updated)}</span>
            )}
          </div>
        </div>

        <div className={styles.layout}>
          {/* Main panel: chat input + recents */}
          <div className={styles.mainPanel}>
            <div className={styles.newChatCard}>
              {/* Attach files preview */}
              {chatAttachFiles.length > 0 && (
                <div className={styles.chatAttachRow}>
                  {chatAttachFiles.map((f, idx) => {
                    const isImg = f.type.startsWith('image/');
                    return isImg ? (
                      <div key={idx} className={styles.chatAttachImg}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={URL.createObjectURL(f)} alt={f.name} className={styles.chatAttachThumb} />
                        <button type="button" className={styles.chatAttachRemove} onClick={() => setChatAttachFiles(p => p.filter((_, i) => i !== idx))}>&times;</button>
                      </div>
                    ) : (
                      <div key={idx} className={styles.chatAttachChip}>
                        <FileIcon filename={f.name} mimeType={f.type} size={14} />
                        <span>{f.name}</span>
                        <button type="button" onClick={() => setChatAttachFiles(p => p.filter((_, i) => i !== idx))}>&times;</button>
                      </div>
                    );
                  })}
                </div>
              )}
              <div className={styles.newChatRow}>
                {/* Attach icon ON THE LEFT */}
                <button
                  type="button"
                  className={styles.newChatAttachBtn}
                  onClick={() => chatFileInputRef.current?.click()}
                  aria-label="Attach file"
                  title="Attach file (Ctrl+U)"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                  </svg>
                </button>

                {/* Hidden file input */}
                <input
                  type="file"
                  multiple
                  ref={chatFileInputRef}
                  style={{ display: 'none' }}
                  onChange={e => { if (e.target.files) { setChatAttachFiles(p => [...p, ...Array.from(e.target.files!)]); e.target.value = ''; } }}
                />

                {/* Textarea in the middle */}
                <textarea
                  ref={chatTextareaRef}
                  className={styles.newChatInput}
                  placeholder={isVoiceRecording ? 'Listening… (speak now)' : `New chat in ${brand.name}`}
                  value={chatDraft}
                  onChange={handleChatDraftChange}
                  onPaste={handleChatInputPaste}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey && !isVoiceRecording) {
                      e.preventDefault();
                      handleOpenChat(projectId, brand_config_id, chatDraft);
                    }
                  }}
                  rows={1}
                />

                {/* Right actions: Voice + Submit */}
                <div className={styles.newChatRightActions}>
                  <VoiceInput
                    disabled={false}
                    onRecordingChange={(recording) => {
                      setIsVoiceRecording(recording);
                      if (recording) voiceInitialTextRef.current = chatDraft;
                    }}
                    onLiveTranscript={(liveText) => {
                      const prefix = voiceInitialTextRef.current ? voiceInitialTextRef.current.trim() + ' ' : '';
                      setChatDraft(prefix + liveText);
                    }}
                    onTranscript={(finalText) => {
                      const prefix = voiceInitialTextRef.current ? voiceInitialTextRef.current.trim() + ' ' : '';
                      if (finalText) setChatDraft(prefix + finalText);
                      setTimeout(() => chatTextareaRef.current?.focus(), 80);
                    }}
                    onCancel={() => {
                      setChatDraft(voiceInitialTextRef.current);
                      setTimeout(() => chatTextareaRef.current?.focus(), 80);
                    }}
                  />
                  <button
                    type="button"
                    className={styles.newChatSubmitBtn}
                    onClick={() => handleOpenChat(projectId, brand_config_id, chatDraft)}
                    aria-label="Start new chat"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            <div>
              <div className={styles.recentsHeading}>Recents</div>
              {chats.length === 0 ? (
                <p className={styles.emptyList}>No chats yet for this project.</p>
              ) : (
                <div className={styles.recentsList}>
                  {chats.map(chat => (
                    <div key={chat.id} className={styles.recentRowWrap}>
                      {renamingChatId === chat.id ? (
                        <div className={styles.inplaceRenameWrap} onClick={e => e.stopPropagation()}>
                          <input
                            type="text"
                            className={styles.inplaceRenameInput}
                            value={chatRenameInput}
                            onChange={e => setChatRenameInput(e.target.value)}
                            onKeyDown={e => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                handleSaveInplaceRename(chat.id);
                              } else if (e.key === 'Escape') {
                                e.preventDefault();
                                closeChatRename();
                              }
                            }}
                            autoFocus
                            disabled={isChatRenaming}
                          />
                          <div className={styles.inplaceBtnGroup}>
                            <button
                              type="button"
                              className={styles.inplaceSaveBtn}
                              onClick={() => handleSaveInplaceRename(chat.id)}
                              disabled={isChatRenaming}
                              title="Save (Enter)"
                              aria-label="Save"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                            </button>
                            <button
                              type="button"
                              className={styles.inplaceCancelBtn}
                              onClick={closeChatRename}
                              disabled={isChatRenaming}
                              title="Cancel (Esc)"
                              aria-label="Cancel"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className={styles.recentRow}
                          onClick={() => handleOpenChat(chat.id, brand_config_id)}
                        >
                          <span className={styles.recentTitle}>{chat.title}</span>
                          <span className={styles.recentTime}>{formatRelative(chat.last_message_at || chat.created_at)}</span>
                        </button>
                      )}

                      <div className={styles.chatMenuWrap} ref={chatMenuId === chat.id ? menuRef : null}>
                        <button
                          type="button"
                          className={styles.chatMenuBtn}
                          onClick={e => { e.stopPropagation(); setChatMenuId(prev => prev === chat.id ? null : chat.id); }}
                          aria-label="Chat options"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                            <circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
                          </svg>
                        </button>
                        {chatMenuId === chat.id && (
                          <div className={styles.chatMenuPopover} onClick={e => e.stopPropagation()}>
                            <button type="button" className={styles.chatMenuOption} onClick={() => openChatRename(chat.id, chat.title)}>
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
                              Rename
                            </button>
                            <button type="button" className={`${styles.chatMenuOption} ${styles.chatMenuOptionDelete}`} onClick={() => handleDeleteChat(chat.id)}>
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right sidebar: compact rows, each opening a slide-over drawer */}
          <aside className={styles.sidebar}>
            <div className={styles.sidebarCard}>
              <SidebarRow
                label="Instructions"
                count={plural(briefFilled.length, 'field')}
                onClick={() => openDrawer('instructions')}
              />
              <SidebarRow
                label="Context"
                count={plural(contextItemCount, 'item')}
                onClick={() => openDrawer('context')}
              />
              <SidebarRow
                label="Social Media"
                count={plural(socialEntries.length, 'handle')}
                onClick={() => openDrawer('social')}
              />
            </div>
          </aside>
        </div>
      </div>

      {/* Slide-over drawer — read-only detail view for the clicked sidebar row */}
      {activeDrawer && (
        <div className={styles.drawerOverlay} onClick={closeDrawer}>
          <div className={styles.drawerPanel} onClick={e => e.stopPropagation()}>
            <div className={styles.drawerHeader}>
              <h3>
                {activeDrawer === 'instructions' && 'Instructions'}
                {activeDrawer === 'context' && 'Context'}
                {activeDrawer === 'social' && 'Social Media'}
              </h3>
              <div className={styles.drawerHeaderActions}>
                {drawerEditing ? (
                  <>
                    <button type="button" className={styles.drawerCancelBtn} onClick={cancelEdit}>Cancel</button>
                    <button type="button" className={styles.drawerSaveBtn} onClick={handleSave} disabled={saving}>
                      {saving ? 'Saving…' : 'Save'}
                    </button>
                  </>
                ) : (
                  <button type="button" className={styles.drawerEditBtn} onClick={startEdit}>Edit</button>
                )}
                <button type="button" className={styles.drawerCloseBtn} onClick={closeDrawer} aria-label="Close">✕</button>
              </div>
            </div>
            <div className={styles.drawerBody}>
              {drawerEditing && saveError && <div className={styles.saveError}>{saveError}</div>}

              {activeDrawer === 'instructions' && (
                drawerEditing ? (
                  <div className={styles.briefList}>
                    {BRAND_BRIEF_FIELDS.map(f => (
                      <div key={f.key} className={styles.briefField}>
                        <div className={styles.briefLabel}>{f.label}</div>
                        <textarea
                          className={styles.editTextarea}
                          value={editForm[f.key] || ''}
                          onChange={e => setEditForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                        />
                      </div>
                    ))}
                  </div>
                ) : hasBrief ? (
                  <div className={styles.briefList}>
                    {BRAND_BRIEF_FIELDS.map(f => {
                      const value = (brand.brand_brief as BrandBrief | null)?.[f.key];
                      if (!value || !value.trim()) return null;
                      return (
                        <div key={f.key} className={styles.briefField}>
                          <div className={styles.briefLabel}>{f.label}</div>
                          <div className={styles.briefValue}>{value}</div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className={styles.emptyList}>No instructions added yet.</p>
                )
              )}

              {activeDrawer === 'context' && (
                drawerEditing ? (
                  <div className={styles.drawerContextList}>
                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Website</span>
                      <input
                        type="text"
                        className={styles.editInput}
                        value={editForm.website_url || ''}
                        onChange={e => setEditForm(prev => ({ ...prev, website_url: e.target.value }))}
                      />
                    </div>
                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Category</span>
                      <input
                        type="text"
                        className={styles.editInput}
                        value={editForm.category || ''}
                        onChange={e => setEditForm(prev => ({ ...prev, category: e.target.value }))}
                      />
                    </div>
                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Target Market</span>
                      <input
                        type="text"
                        className={styles.editInput}
                        value={editForm.target_market || ''}
                        onChange={e => setEditForm(prev => ({ ...prev, target_market: e.target.value }))}
                      />
                    </div>
                  </div>
                ) : (
                  <div className={styles.drawerContextList}>
                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Logo</span>
                      {logoVisible ? (
                        <img
                          src={logoSrc ?? undefined}
                          alt="Brand logo"
                          className={styles.drawerLogoImg}
                          onError={() => setFailedLogoUrl(brand.logo_url)}
                        />
                      ) : (
                        <span className={styles.fieldEmpty}>No logo uploaded</span>
                      )}
                    </div>

                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Website</span>
                      {brand.website_url
                        ? <a href={brand.website_url} target="_blank" rel="noopener noreferrer" className={styles.fieldLink}>{brand.website_url}</a>
                        : <span className={styles.fieldEmpty}>—</span>}
                    </div>

                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Category</span>
                      <span className={styles.fieldValue}>{brand.category || '—'}</span>
                    </div>

                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Target Market</span>
                      <span className={styles.fieldValue}>{formatTargetMarket(brand.target_market)}</span>
                    </div>

                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Brand Colors</span>
                      {hasColors ? (
                        <div className={styles.swatchRow}>
                          {brand.colors?.primary && (
                            <div className={styles.swatch}>
                              <div className={styles.swatchDot} style={{ background: brand.colors.primary }} />
                              <span className={styles.swatchLabel}>{brand.colors.primary}</span>
                            </div>
                          )}
                          {brand.colors?.secondary && (
                            <div className={styles.swatch}>
                              <div className={styles.swatchDot} style={{ background: brand.colors.secondary }} />
                              <span className={styles.swatchLabel}>{brand.colors.secondary}</span>
                            </div>
                          )}
                          {brand.colors?.accent && (
                            <div className={styles.swatch}>
                              <div className={styles.swatchDot} style={{ background: brand.colors.accent }} />
                              <span className={styles.swatchLabel}>{brand.colors.accent}</span>
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className={styles.fieldEmpty}>—</span>
                      )}
                    </div>

                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Competitors</span>
                      {competitors_selected.length === 0 ? (
                        <span className={styles.fieldEmpty}>—</span>
                      ) : (
                        <div className={styles.compactList}>
                          {competitors_selected.map((c, i) => {
                            const isBrandLogo = !!(c.logo_url && brand.logo_url && c.logo_url === brand.logo_url);
                            const showLogo = Boolean(c.logo_url && !isBrandLogo);
                            return (
                              <div key={i} className={styles.compactItem}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                  {showLogo && (
                                    <img
                                      src={resolveLogo(c.logo_url) || ''}
                                      alt={c.name}
                                      className={styles.compLogo}
                                      onError={(e) => { (e.currentTarget as HTMLElement).style.display = 'none'; }}
                                    />
                                  )}
                                  <span className={styles.compactName}>{c.name}</span>
                                </div>
                                {c.website_url && <span className={styles.compactUrl}>{c.website_url}</span>}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    <div className={styles.drawerContextItem}>
                      <span className={styles.fieldLabel}>Source Documents</span>
                      {brand.reference_docs.length === 0 ? (
                        <span className={styles.fieldEmpty}>No source documents added yet</span>
                      ) : (
                        <div className={styles.sourceDocsList}>
                          {brand.reference_docs.map(doc => (
                            <div key={doc.ref_id} className={styles.sourceDocItem}>
                              <span className={styles.compactName}>{doc.filename}</span>
                              <button
                                type="button"
                                className={styles.removeDocBtn}
                                onClick={() => handleRemoveReferenceDoc(doc)}
                                disabled={deletingRefId === doc.ref_id}
                                aria-label={`Remove ${doc.filename}`}
                              >
                                {deletingRefId === doc.ref_id ? '…' : '✕'}
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                      <label className={`${styles.addFileBtn} ${docUploading ? styles.addFileBtnDisabled : ''}`}>
                        {docUploading ? 'Uploading…' : '+ Add file'}
                        <input
                          type="file"
                          accept=".pdf,.docx,.txt,.md"
                          onChange={handleReferenceFileSelect}
                          disabled={docUploading}
                          style={{ display: 'none' }}
                        />
                      </label>
                      {docUploadError && <div className={styles.uploadError}>{docUploadError}</div>}
                    </div>
                  </div>
                )
              )}

              {activeDrawer === 'social' && (
                drawerEditing ? (
                  <div className={styles.drawerContextList}>
                    {socialRows.map(platform => (
                      <div key={platform} className={styles.drawerContextItem}>
                        <div className={styles.socialHeaderRow}>
                          {SOCIAL_PLATFORM_ICONS[platform]}
                          <span className={styles.fieldLabel}>{SOCIAL_PLATFORM_LABELS[platform]}</span>
                        </div>
                        <div className={styles.handleRow}>
                          <input
                            type="text"
                            className={styles.editInput}
                            value={editForm[platform] || ''}
                            onChange={e => setEditForm(prev => ({ ...prev, [platform]: e.target.value }))}
                          />
                          <button
                            type="button"
                            className={styles.removeHandleBtn}
                            onClick={() => {
                              setEditForm(prev => ({ ...prev, [platform]: '' }));
                              setSocialRows(prev => prev.filter(p => p !== platform));
                            }}
                            aria-label={`Remove ${SOCIAL_PLATFORM_LABELS[platform]}`}
                          >
                            ✕
                          </button>
                        </div>
                      </div>
                    ))}
                    {socialRows.length < SOCIAL_PLATFORM_ORDER.length && (
                      <select
                        className={styles.editInput}
                        value=""
                        onChange={e => {
                          const platform = e.target.value as keyof SocialHandles;
                          if (platform) setSocialRows(prev => [...prev, platform]);
                        }}
                      >
                        <option value="">+ Add handle</option>
                        {SOCIAL_PLATFORM_ORDER.filter(p => !socialRows.includes(p)).map(p => (
                          <option key={p} value={p}>{SOCIAL_PLATFORM_LABELS[p]}</option>
                        ))}
                      </select>
                    )}
                  </div>
                ) : socialEntries.length === 0 ? (
                  <p className={styles.emptyList}>No social handles added.</p>
                ) : (
                  <div className={styles.drawerContextList}>
                    {socialEntries.map(({ platform, url }) => (
                      <div key={platform} className={styles.drawerContextItem}>
                        <div className={styles.socialHeaderRow}>
                          {SOCIAL_PLATFORM_ICONS[platform]}
                          <span className={styles.fieldLabel}>{SOCIAL_PLATFORM_LABELS[platform]}</span>
                        </div>
                        <a href={url} target="_blank" rel="noopener noreferrer" className={styles.fieldLink}>{url}</a>
                      </div>
                    ))}
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      )}
      <ConfirmModal
        isOpen={removeDocConfirm.isOpen}
        title="Remove Document"
        message={removeDocConfirm.doc ? `Remove "${removeDocConfirm.doc.filename}"?` : ''}
        confirmLabel="Remove"
        confirmDanger
        onConfirm={() => removeDocConfirm.doc && doRemoveReferenceDoc(removeDocConfirm.doc)}
        onCancel={() => setRemoveDocConfirm({ isOpen: false, doc: null })}
      />
      <ConfirmModal
        isOpen={deleteChatId !== null}
        title="Delete Chat"
        message="Delete this chat everywhere, including Chat History in the sidebar? This cannot be undone."
        confirmLabel="Delete"
        confirmDanger
        onConfirm={() => deleteChatId && handleDeleteChat(deleteChatId)}
        onCancel={() => setDeleteChatId(null)}
      />

      </main>
    </div>
  );
}
