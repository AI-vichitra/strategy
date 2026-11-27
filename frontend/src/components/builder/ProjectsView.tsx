'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import styles from './ProjectsView.module.css';
import ConfirmModal from '../ConfirmModal';
import AlertModal from '../AlertModal';

interface ProjectsViewProps {
  onSelectProject?: (id: string) => void;
  onCreateProject?: () => void;
}

const formatShortDate = (dateStr?: string) => {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = String(d.getFullYear()).slice(-2);
    return `${day}/${month}/${year}`;
  } catch {
    return dateStr;
  }
};

export default function ProjectsView({ onSelectProject, onCreateProject }: ProjectsViewProps) {
  const router = useRouter();
  const [projects, setProjects] = useState<any[]>([]);
  const [brands, setBrands] = useState<any[]>([]);
  const [brandsMap, setBrandsMap] = useState<Record<string, string>>({});
  const [activeMenuProjectId, setActiveMenuProjectId] = useState<string | null>(null);
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<{ id: string; title: string; brand_config_id?: string } | null>(null);
  const [renameInput, setRenameInput] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameError, setRenameError] = useState('');
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    confirmLabel: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', confirmLabel: 'Delete', onConfirm: () => {} });
  const [alertModal, setAlertModal] = useState<{ isOpen: boolean; title: string; message: string }>({
    isOpen: false, title: '', message: ''
  });

  const showAlert = (title: string, message: string) =>
    setAlertModal({ isOpen: true, title, message });
  const closeAlert = () => setAlertModal(a => ({ ...a, isOpen: false }));
  const closeConfirm = () => setConfirmModal(c => ({ ...c, isOpen: false }));

  const handleCreateNewProject = () => {
    // Navigate to brand-setup with the new project flag
    router.push('/brand-setup?new=true');
  };

  const fetchProjects = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const [res, brandsRes] = await Promise.allSettled([
        fetch(`${apiBase}/api/projects/`, { headers }),
        fetch(`${apiBase}/api/brands/`, { headers })
      ]);

      if (res.status === 'fulfilled' && res.value.ok) {
        const data = await res.value.json();
        setProjects(data || []);
      }
      if (brandsRes.status === 'fulfilled' && brandsRes.value.ok) {
        const brandsData = await brandsRes.value.json();
        const bMap: Record<string, string> = {};
        (brandsData || []).forEach((b: any) => { bMap[b.id] = b.brand_name; });
        setBrandsMap(bMap);
        setBrands(brandsData || []);
      }
    } catch (e) {
      console.error("Failed to fetch projects", e);
    }
  };

  useEffect(() => {
    fetchProjects();

    const handleProjectChanged = () => {
      fetchProjects();
    };
    window.addEventListener('projectChanged', handleProjectChanged);
    return () => window.removeEventListener('projectChanged', handleProjectChanged);
  }, []);

  useEffect(() => {
    const closeMenu = () => setActiveMenuProjectId(null);
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  const openRenameModal = (id: string, currentTitle: string, brandConfigId?: string) => {
    setRenameTarget({ id, title: currentTitle, brand_config_id: brandConfigId });
    setRenameInput(currentTitle);
    setRenameError('');
    setRenameModalOpen(true);
    setActiveMenuProjectId(null);
  };

  const closeRenameModal = () => {
    if (isRenaming) return;
    setRenameModalOpen(false);
    setRenameTarget(null);
    setRenameInput('');
    setRenameError('');
  };

  const handleConfirmRename = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!renameTarget) return;
    const trimmed = renameInput.trim();
    if (!trimmed) {
      setRenameError('Project name cannot be empty.');
      return;
    }

    if (trimmed === renameTarget.title) {
      closeRenameModal();
      return;
    }

    setIsRenaming(true);
    setRenameError('');

    // Instant optimistic update across projects, brands, and brand cards
    setProjects(prev => prev.map(p => (p.id === renameTarget.id || (renameTarget.brand_config_id && p.brand_config_id === renameTarget.brand_config_id)) ? { ...p, title: trimmed } : p));
    setBrands(prev => prev.map(b => (b.id === renameTarget.brand_config_id || b.id === renameTarget.id) ? { ...b, brand_name: trimmed } : b));
    setBrandsMap(prev => {
      const next = { ...prev };
      if (renameTarget.brand_config_id) next[renameTarget.brand_config_id] = trimmed;
      if (renameTarget.id) next[renameTarget.id] = trimmed;
      return next;
    });

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = localStorage.getItem('access_token');
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const brandId = renameTarget.brand_config_id || renameTarget.id;
      const promises: Promise<any>[] = [];

      if (brandId) {
        promises.push(
          fetch(`${apiBase}/api/brands/${brandId}`, {
            method: 'PUT',
            headers,
            body: JSON.stringify({ brand_name: trimmed })
          })
        );
      }

      if (renameTarget.id && renameTarget.id !== brandId) {
        promises.push(
          fetch(`${apiBase}/api/projects/${renameTarget.id}`, {
            method: 'PUT',
            headers,
            body: JSON.stringify({ title: trimmed })
          })
        );
      }

      const results = await Promise.allSettled(promises);
      const anySuccess = results.some(r => r.status === 'fulfilled' && r.value.ok);

      if (anySuccess) {
        window.dispatchEvent(new CustomEvent('projectChanged', { detail: { projectId: renameTarget.id, title: trimmed, brand_config_id: brandId } }));
        closeRenameModal();
        fetchProjects();
      } else {
        const failedRes = results.find(r => r.status === 'fulfilled' && !r.value.ok) as PromiseFulfilledResult<Response> | undefined;
        const err = failedRes ? await failedRes.value.json().catch(() => null) : null;
        setRenameError(err?.detail || 'Failed to rename project. Please try again.');
        fetchProjects();
      }
    } catch (e) {
      console.error("Failed to rename project", e);
      setRenameError('An unexpected error occurred. Please try again.');
      fetchProjects();
    } finally {
      setIsRenaming(false);
    }
  };

  const doDeleteBrand = async (brandId: string) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = localStorage.getItem('access_token');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${apiBase}/api/brands/${brandId}`, {
        method: 'DELETE',
        headers
      });
      if (res.ok) {
        setBrands(prev => prev.filter(b => b.id !== brandId));
        window.dispatchEvent(new CustomEvent('projectChanged', { detail: { projectId: null } }));
        fetchProjects();
      } else {
        const err = await res.json().catch(() => null);
        showAlert('Error', err?.detail ?? 'Could not delete this brand. Please try again.');
      }
    } catch (e) {
      console.error("Failed to delete brand", e);
    } finally {
      setActiveMenuProjectId(null);
    }
  };

  const handleDeleteBrand = (brandId: string, brandName: string) => {
    setConfirmModal({
      isOpen: true,
      title: 'Delete Brand',
      message: `Delete brand "${brandName}"? This cannot be undone.`,
      confirmLabel: 'Delete',
      onConfirm: () => { closeConfirm(); doDeleteBrand(brandId); },
    });
  };

  const doDeleteProject = async (id: string) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = localStorage.getItem('access_token');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${apiBase}/api/projects/${id}`, {
        method: 'DELETE',
        headers
      });
      if (res.ok) {
        const remaining = projects.filter(p => p.id !== id);
        setProjects(remaining);
        window.dispatchEvent(new CustomEvent('projectChanged', { detail: { projectId: null } }));
        if (!remaining || remaining.length === 0) {
          router.push('/brand-setup?new=true');
        } else {
          fetchProjects();
        }
      } else {
        const err = await res.json().catch(() => null);
        showAlert('Error', err?.detail ?? 'Could not delete this project. Please try again.');
      }
    } catch (e) {
      console.error("Failed to delete project", e);
    } finally {
      setActiveMenuProjectId(null);
    }
  };

  const handleDeleteProject = (id: string) => {
    setConfirmModal({
      isOpen: true,
      title: 'Delete Project',
      message: 'Are you sure you want to delete this project and its research entirely?',
      confirmLabel: 'Delete',
      onConfirm: () => { closeConfirm(); doDeleteProject(id); },
    });
  };

  // Build unique brand cards so every onboarded brand gets 1 dedicated card
  const seenBrandKeys = new Set<string>();
  const brandCards: any[] = [];

  brands.forEach((b: any) => {
    const norm = (b.brand_name || '').trim().toLowerCase();
    if (seenBrandKeys.has(norm)) return;
    seenBrandKeys.add(norm);

    const brandProjects = projects.filter((p: any) => 
      p.brand_config_id === b.id || 
      (p.title && p.title.trim().toLowerCase() === norm) ||
      (brandsMap[p.brand_config_id] && brandsMap[p.brand_config_id].trim().toLowerCase() === norm)
    );
    const latestProj = brandProjects.sort((p1: any, p2: any) => 
      new Date(p2.created_at || 0).getTime() - new Date(p1.created_at || 0).getTime()
    )[0];

    let cardLogo = b.logo_url || null;
    if (!cardLogo && latestProj?.brand_kit) {
      try {
        const bk = typeof latestProj.brand_kit === 'string' ? JSON.parse(latestProj.brand_kit) : latestProj.brand_kit;
        cardLogo = bk?.logo_url;
      } catch {}
    }
    if (!cardLogo && latestProj?.logo_data) {
      cardLogo = `/api/projects/${latestProj.id}/logo`;
    }
    brandCards.push({
      id: latestProj ? latestProj.id : b.id,
      _hasProject: !!latestProj,
      brand_config_id: b.id,
      title: b.brand_name,
      description: b.category || (latestProj ? latestProj.description : '') || 'Strategic Intelligence',
      created_at: b.created_at || (latestProj ? latestProj.created_at : new Date().toISOString()),
      agent_type: latestProj ? latestProj.agent_type : 'StratAI',
      logo_url: cardLogo
    });
  });

  projects.forEach((proj: any) => {
    const bName = (brandsMap[proj.brand_config_id] || proj.title || '').trim().toLowerCase();
    if (bName && !seenBrandKeys.has(bName) && !brandCards.some(c => c.id === proj.id)) {
      seenBrandKeys.add(bName);
      let projLogo = null;
      if (proj.brand_kit) {
        try {
          const bk = typeof proj.brand_kit === 'string' ? JSON.parse(proj.brand_kit) : proj.brand_kit;
          projLogo = bk?.logo_url;
        } catch {}
      }
      brandCards.push({
        id: proj.id,
        brand_config_id: proj.brand_config_id,
        title: brandsMap[proj.brand_config_id] || proj.title || 'Brand Project',
        description: proj.title,
        created_at: proj.created_at,
        agent_type: proj.agent_type,
        logo_url: projLogo
      });
    }
  });

  const displayProjects = brandCards.length > 0 ? brandCards : projects;

  const handleCardClick = (proj: any) => {
    router.push(`/projects/${proj.id}`);
  };

  return (
    <div className={styles.wrapper}>
      {/* Top Header */}
      <div className={styles.header}>
        <h1 className={styles.welcomeTitle}>Your Projects</h1>
        <div className={styles.actions}>
          <button type="button" className={styles.createBtn} onClick={handleCreateNewProject}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Create New Project
          </button>
        </div>
      </div>

      {/* Projects Section */}
      <div className={styles.section}>
        {displayProjects.length === 0 ? (
          <div className={styles.emptyState}>No projects found. Create a project to get started.</div>
        ) : (
          <div className={styles.grid}>
            {displayProjects.map((proj, idx) => (
              <div 
                key={idx} 
                className={styles.card} 
                onClick={() => handleCardClick(proj)} 
                style={{ cursor: 'pointer', position: 'relative' }}
              >
                <div className={styles.cardHeader}>
                  <div className={`${styles.agentAvatar} ${proj.logo_url ? styles.agentAvatarLogo : ''}`}>
                    {proj.logo_url ? (
                      <img
                        src={proj.logo_url.startsWith('/') ? `${process.env.NEXT_PUBLIC_API_URL || ''}${proj.logo_url}` : proj.logo_url}
                        alt={proj.title}
                        className={styles.avatarImg}
                        onError={(e) => { (e.currentTarget as HTMLElement).style.display = 'none'; }}
                      />
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="2" y1="12" x2="22" y2="12" />
                        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                      </svg>
                    )}
                  </div>
                  
                  <button 
                    type="button" 
                    className={styles.optionsBtn} 
                    aria-label="Project options"
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveMenuProjectId(activeMenuProjectId === proj.id ? null : proj.id);
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="1"/>
                      <circle cx="12" cy="5" r="1"/>
                      <circle cx="12" cy="19" r="1"/>
                    </svg>
                  </button>

                  {activeMenuProjectId === proj.id && (
                    <div className={styles.optionsMenu} onClick={(e) => e.stopPropagation()}>
                      <button 
                        type="button" 
                        onClick={(e) => {
                          e.stopPropagation();
                          openRenameModal(proj.id, proj.title, proj.brand_config_id);
                        }}
                        className={styles.optionsMenuItem}
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (proj._hasProject === false) {
                            handleDeleteBrand(proj.brand_config_id, proj.title);
                          } else {
                            handleDeleteProject(proj.id);
                          }
                        }}
                        className={`${styles.optionsMenuItem} ${styles.deleteOption}`}
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>

                <div className={styles.cardBody}>
                  <h3 className={styles.cardTitle}>{proj.title}</h3>
                  <p className={styles.cardDesc}>{proj.description || proj.title}</p>
                </div>

                <div className={styles.cardBottom}>
                  <div className={styles.connectorsRow}>
                    {/* Shared member avatars — only shown when project has team members */}
                    {Array.isArray(proj.shared_with) && proj.shared_with.length > 0 && (
                      <div className={styles.memberAvatars}>
                        {proj.shared_with.slice(0, 4).map((member: any, mi: number) => {
                          const initials = (member.name || member.email || '?')
                            .split(/[\s@]+/)
                            .slice(0, 2)
                            .map((p: string) => p[0]?.toUpperCase() || '')
                            .join('');
                          return member.avatar_url ? (
                            <img key={mi} src={member.avatar_url} alt={member.name || member.email} className={styles.memberAvatar} title={member.name || member.email} />
                          ) : (
                            <div key={mi} className={styles.memberAvatarInitials} title={member.name || member.email}>{initials}</div>
                          );
                        })}
                        {proj.shared_with.length > 4 && (
                          <div className={styles.memberAvatarMore}>+{proj.shared_with.length - 4}</div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className={styles.metaInfo}>
                    <span className={styles.metaDate}>
                      Created on {formatShortDate(proj.created_at)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Rename Modal */}
      {renameModalOpen && (
        <div 
          className={styles.modalOverlay}
          onClick={(e) => {
            if (e.target === e.currentTarget) closeRenameModal();
          }}
        >
          <div className={styles.modalCard} role="dialog" aria-modal="true" aria-labelledby="rename-modal-title">
            <div className={styles.modalHeader}>
              <div className={styles.modalIconBox}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
                </svg>
              </div>
              <div className={styles.modalHeaderText}>
                <h3 id="rename-modal-title" className={styles.modalTitle}>Rename Project</h3>
                <p className={styles.modalSubtitle}>Enter a new name for this project</p>
              </div>
              <button 
                type="button" 
                className={styles.modalCloseBtn}
                onClick={closeRenameModal}
                disabled={isRenaming}
                aria-label="Close modal"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            <form onSubmit={handleConfirmRename}>
              <div className={styles.modalBody}>
                <label className={styles.inputLabel} htmlFor="project-name-input">
                  Project Name
                </label>
                <input
                  id="project-name-input"
                  type="text"
                  className={`${styles.renameInput} ${renameError ? styles.renameInputError : ''}`}
                  value={renameInput}
                  onChange={(e) => {
                    setRenameInput(e.target.value);
                    if (renameError) setRenameError('');
                  }}
                  placeholder="Enter project name..."
                  autoFocus
                  disabled={isRenaming}
                />
                {renameError && (
                  <p className={styles.errorText}>{renameError}</p>
                )}
              </div>

              <div className={styles.modalFooter}>
                <button
                  type="button"
                  className={styles.modalCancelBtn}
                  onClick={closeRenameModal}
                  disabled={isRenaming}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.modalSubmitBtn}
                  disabled={isRenaming || !renameInput.trim()}
                >
                  {isRenaming ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        confirmLabel={confirmModal.confirmLabel}
        confirmDanger
        onConfirm={confirmModal.onConfirm}
        onCancel={closeConfirm}
      />
      <AlertModal
        isOpen={alertModal.isOpen}
        title={alertModal.title}
        message={alertModal.message}
        variant="error"
        onClose={closeAlert}
      />
    </div>
  );
}
