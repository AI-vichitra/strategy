'use client';
import { useState, useEffect, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import styles from './Sidebar.module.css';
import ConfirmModal from '../ConfirmModal';

interface Project {
  id: string;
  title: string;
  agent_type: string;
  created_at: string;
  brand_config_id: string;
  messages?: any[];
}

interface UserProfile {
  id: string;
  email: string;
  full_name?: string | null;
  avatar_url?: string | null;
}

const GOOGLE_COLORS = [
  '#1a73e8', // blue
  '#d93025', // red
  '#188038', // green
  '#f29900', // yellow-orange
  '#a142f4', // purple
  '#fa7b17', // orange
  '#007b83', // teal
  '#e52592', // pink
];

function getAvatarColor(nameOrEmail: string): string {
  let hash = 0;
  for (let i = 0; i < nameOrEmail.length; i++) {
    hash = nameOrEmail.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % GOOGLE_COLORS.length;
  return GOOGLE_COLORS[index];
}

function getInitials(name?: string | null, email?: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (email) {
    return email.slice(0, 1).toUpperCase();
  }
  return 'U';
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [brands, setBrands] = useState<Record<string, string>>({});
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [activeNavTab, setActiveNavTab] = useState<string>('newChat');
  const [loading, setLoading] = useState(true);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [user, setUser] = useState<UserProfile | null>(null);
  const [avatarError, setAvatarError] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [deleteChatConfirm, setDeleteChatConfirm] = useState<{ isOpen: boolean; projectId: string; e: React.MouseEvent | null }>({ isOpen: false, projectId: '', e: null });
  const profileRef = useRef<HTMLDivElement>(null);
  const renameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setAvatarError(false);
  }, [user?.avatar_url]);

  const fetchUserProfile = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      if (!token) return;
      const res = await fetch(`${apiBase}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      }
    } catch (e) {
      console.error('Failed to fetch user profile', e);
    }
  };

  // Close menus on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (profileRef.current && !profileRef.current.contains(target)) {
        setProfileMenuOpen(false);
      }
      if (!target.closest(`.${styles.menuBtn}`) && !target.closest(`.${styles.menuPopover}`)) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, []);

  useEffect(() => {
    if (editingProjectId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [editingProjectId]);

  useEffect(() => {
    fetchUserProfile();
    const handleProfileUpdate = () => {
      fetchUserProfile();
    };
    window.addEventListener('userProfileUpdated', handleProfileUpdate);
    return () => window.removeEventListener('userProfileUpdated', handleProfileUpdate);
  }, []);

  const fetchProjects = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      if (!token) {
        window.location.href = '/auth';
        return;
      }
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${apiBase}/api/projects/`, { headers });
      const brandsRes = await fetch(`${apiBase}/api/brands/`, { headers });
      
      if (res.status === 401 || brandsRes.status === 401) {
        localStorage.removeItem('access_token');
        window.location.href = '/auth';
        return;
      }

      if (res.ok && brandsRes.ok) {
        const data = await res.json();
        const brandsData = await brandsRes.json();
        const brandsMap: Record<string, string> = {};
        brandsData.forEach((b: any) => { brandsMap[b.id] = b.brand_name; });
        setBrands(brandsMap);

        setProjects(data || []);

        // Only projects with actual chat messages count as chats done
        const chatProjects = (data || []).filter(
          (p: any) => Array.isArray(p.messages) && p.messages.length > 0
        );

        if (activeProjectId) {
          const exists = chatProjects.some((p: any) => p.id === activeProjectId);
          if (!exists) {
            setActiveProjectId(null);
            setActiveNavTab('newChat');
          }
        } else {
          setActiveProjectId(null);
          setActiveNavTab('newChat');
        }
      }
    } catch (e) {
      console.error('Failed to fetch projects', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  // Listen for project changes and view changes from MainContent
  useEffect(() => {
    const handleProjectChange = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail?.title && customEvent.detail?.projectId) {
        const renamedTitle = customEvent.detail.title;
        setProjects(prev => prev.map(p => (p.id === customEvent.detail.projectId || (customEvent.detail.brand_config_id && p.brand_config_id === customEvent.detail.brand_config_id)) ? { ...p, title: renamedTitle } : p));
      }
      if (customEvent.detail?.projectId) {
        setActiveProjectId(customEvent.detail.projectId);
        setActiveNavTab('chat');
        fetchProjects(); // refresh list
      } else {
        setActiveNavTab('newChat');
      }
    };
    
    const handleNewChat = () => {
      setActiveProjectId(null);
      setActiveNavTab('newChat');
    };

    const handleViewChanged = (e: Event) => {
      const customEvent = e as CustomEvent;
      const v = customEvent.detail?.view;
      if (v === 'files') {
        setActiveNavTab('files');
        setActiveProjectId(null);
      } else if (v === 'connectors') {
        setActiveNavTab('connectors');
        setActiveProjectId(null);
      } else if (v === 'agents') {
        setActiveNavTab('agents');
        setActiveProjectId(null);
      } else if (v === 'projects') {
        setActiveNavTab('projects');
        setActiveProjectId(null);
      } else if (v === 'settings') {
        setActiveNavTab('settings');
        setActiveProjectId(null);
      } else if (v === 'teams') {
        setActiveNavTab('teams');
        setActiveProjectId(null);
      } else if (v === 'builder') {
        setActiveProjectId((curr) => {
          if (!curr) {
            setActiveNavTab('newChat');
          } else {
            setActiveNavTab('chat');
          }
          return curr;
        });
      }
    };

    const handleProjectDeleted = () => {
      fetchProjects();
    };

    const handleProjectRenamed = (e: Event) => {
      const customEvent = e as CustomEvent;
      const { projectId, title, brand_config_id } = customEvent.detail || {};
      if (!projectId || !title) return;
      setProjects(prev => prev.map(p => p.id === projectId ? { ...p, title } : p));
      if (brand_config_id) setBrands(prev => ({ ...prev, [brand_config_id]: title }));
    };

    window.addEventListener('projectChanged', handleProjectChange);
    window.addEventListener('newChat', handleNewChat);
    window.addEventListener('viewChanged', handleViewChanged);
    window.addEventListener('projectDeleted', handleProjectDeleted);
    window.addEventListener('projectRenamed', handleProjectRenamed);
    return () => {
      window.removeEventListener('projectChanged', handleProjectChange);
      window.removeEventListener('newChat', handleNewChat);
      window.removeEventListener('viewChanged', handleViewChanged);
      window.removeEventListener('projectDeleted', handleProjectDeleted);
      window.removeEventListener('projectRenamed', handleProjectRenamed);
    };
  }, []);

  const handleOpenProject = (projectId: string) => {
    setActiveProjectId(projectId);
    setActiveNavTab('chat');
    if (pathname?.startsWith('/projects/')) {
      router.push(`/build?project=${encodeURIComponent(projectId)}`);
      return;
    }
    window.dispatchEvent(new CustomEvent('openProject', { detail: { projectId } }));
  };

  const handleNavClick = (tabKey: string, eventName: string) => {
    setActiveNavTab(tabKey);
    setActiveProjectId(null);
    if (pathname?.startsWith('/projects/')) {
      const targetView = tabKey === 'newChat' ? 'builder' : tabKey;
      router.push(targetView === 'builder' ? '/build' : `/build?view=${encodeURIComponent(targetView)}`);
      return;
    }
    window.dispatchEvent(new CustomEvent(eventName));
  };

  const handleDeleteProject = (projectIdToDelete: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteChatConfirm({ isOpen: true, projectId: projectIdToDelete, e });
  };

  const doDeleteProject = async (projectIdToDelete: string) => {
    setDeleteChatConfirm({ isOpen: false, projectId: '', e: null });
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      if (!token) return;
      const headers: Record<string, string> = { 'Authorization': `Bearer ${token}` };

      const res = await fetch(`${apiBase}/api/projects/${projectIdToDelete}`, {
        method: 'DELETE',
        headers
      });

      if (res.ok) {
        if (projectIdToDelete === activeProjectId) {
          window.dispatchEvent(new CustomEvent('newChat'));
          setActiveProjectId(null);
        }
        fetchProjects();
        window.dispatchEvent(new CustomEvent('projectChanged', { detail: { projectId: null } }));
      }
    } catch (err) {
      console.error('Failed to delete project:', err);
    } finally {
      setOpenMenuId(null);
    }
  };

  const handleStartRename = (proj: Project, e: React.MouseEvent) => {
    e.stopPropagation();
    setOpenMenuId(null);
    setEditingProjectId(proj.id);
    setEditingTitle(proj.title);
  };

  const handleSaveRename = async (projectId: string) => {
    const trimmed = editingTitle.trim();
    setEditingProjectId(null);
    if (!trimmed) return;

    const currentProj = projects.find(p => p.id === projectId);
    if (currentProj && currentProj.title === trimmed) return;

    // Optimistically update project title
    setProjects(prev => prev.map(p => p.id === projectId ? { ...p, title: trimmed } : p));
    if (currentProj?.brand_config_id) {
      setBrands(prev => ({ ...prev, [currentProj.brand_config_id]: trimmed }));
    }

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      if (!token) return;
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      };

      const res = await fetch(`${apiBase}/api/projects/${projectId}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({ title: trimmed })
      });

      if (res.ok) {
        window.dispatchEvent(new CustomEvent('projectChanged', { detail: { projectId, title: trimmed, brand_config_id: currentProj?.brand_config_id } }));
      } else {
        fetchProjects();
      }
    } catch (err) {
      console.error('Failed to rename project:', err);
      fetchProjects();
    }
  };

  // Chat history should only include projects that have actual chat messages done
  const chatHistoryProjects = projects.filter(
    (p) => Array.isArray(p.messages) && p.messages.length > 0
  );

  // Sort active chat projects so the latest is always on top, and deduplicate identical cards
  const seenHistory = new Set<string>();
  const sortedProjects: Project[] = [];
  [...chatHistoryProjects]
    .sort((a, b) => {
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return timeB - timeA;
    })
    .forEach((p) => {
      const key = `${p.brand_config_id || ''}-${(p.agent_type || p.title || '').trim().toLowerCase()}`;
      if (!seenHistory.has(key)) {
        seenHistory.add(key);
        sortedProjects.push(p);
      }
    });

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('brand_config_id');
    localStorage.removeItem('pathChosen');
    window.location.href = '/auth';
  };

  const displayName = user?.full_name || (user?.email ? user.email.split('@')[0] : 'User');
  const initials = getInitials(user?.full_name, user?.email);

  const handleOpenSettings = () => {
    setProfileMenuOpen(false);
    window.dispatchEvent(new CustomEvent('openSettings'));
  };

  return (
    <aside className={styles.sidebar}>
      {/* Top Header */}
      <div className={styles.header}>
        <div className={styles.logo}>
          <div className={styles.logoIcon}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className={styles.logoText}>StratAI</span>
        </div>
      </div>

      <div className={styles.scrollArea}>
        {/* Nav Group */}
        <nav className={styles.navGroup}>
          <button
            type="button"
            className={`${styles.navItem} ${activeNavTab === 'newChat' && !activeProjectId ? styles.navItemActive : ''}`}
            onClick={() => handleNavClick('newChat', 'newChat')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            New Chat
          </button>
          <button
            type="button"
            className={`${styles.navItem} ${activeNavTab === 'files' ? styles.navItemActive : ''}`}
            onClick={() => handleNavClick('files', 'openFiles')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 10V7l-5-5H6c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7"/>
              <path d="M14 2v4a2 2 0 0 0 2 2h4"/>
              <path d="M16 22h6"/><path d="M19 19v6"/>
            </svg>
            Files Generated
          </button>
          <button
            type="button"
            className={`${styles.navItem} ${activeNavTab === 'connectors' ? styles.navItemActive : ''}`}
            onClick={() => handleNavClick('connectors', 'openConnectorsView')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
            Connector
          </button>
          <button
            type="button"
            className={`${styles.navItem} ${activeNavTab === 'agents' ? styles.navItemActive : ''}`}
            onClick={() => handleNavClick('agents', 'openAgents')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7"/>
              <rect x="14" y="3" width="7" height="7"/>
              <rect x="14" y="14" width="7" height="7"/>
              <rect x="3" y="14" width="7" height="7"/>
            </svg>
            Agents
          </button>
          <button
            type="button"
            className={`${styles.navItem} ${activeNavTab === 'projects' ? styles.navItemActive : ''}`}
            onClick={() => handleNavClick('projects', 'openProjects')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            Projects
          </button>
          {/* Workflows tab - commented out for now, to be worked on later
          <button type="button" className={styles.navItem} onClick={() => window.dispatchEvent(new CustomEvent('openWorkflow'))}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            Workflow
          </button>
          */}
        </nav>

        {/* Chat History */}
        <div className={styles.historySection}>
          <div className={styles.historyHeader}>Chat History</div>
          {loading ? (
            <div className={styles.historyEmpty}>Loading...</div>
          ) : sortedProjects.length === 0 ? null : (
            <div className={styles.historyList}>
              {sortedProjects.map(proj => (
                <div
                  key={proj.id}
                  className={`${styles.historyItemWrapper} ${proj.id === activeProjectId && activeNavTab === 'chat' ? styles.historyItemActive : ''}`}
                  onClick={() => {
                    if (editingProjectId !== proj.id) {
                      handleOpenProject(proj.id);
                    }
                  }}
                >
                  <div className={styles.historyItemLeft}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.historyItemIcon}>
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                    {editingProjectId === proj.id ? (
                      <input
                        ref={renameInputRef}
                        type="text"
                        className={styles.renameInput}
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleSaveRename(proj.id);
                          } else if (e.key === 'Escape') {
                            setEditingProjectId(null);
                          }
                        }}
                        onBlur={() => handleSaveRename(proj.id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span className={styles.historyItemTitle} title={proj.title}>
                        {proj.title}
                      </span>
                    )}
                  </div>
                  
                  {editingProjectId === proj.id ? (
                    <div className={styles.renameActions} onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className={`${styles.renameActionBtn} ${styles.renameSaveBtn}`}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSaveRename(proj.id);
                        }}
                        title="Save changes"
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        className={`${styles.renameActionBtn} ${styles.renameCancelBtn}`}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingProjectId(null);
                        }}
                        title="Cancel"
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </div>
                  ) : (
                    <div className={styles.menuContainer}>
                      <button 
                        className={`${styles.menuBtn} ${openMenuId === proj.id ? styles.menuBtnActive : ''}`} 
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuId(openMenuId === proj.id ? null : proj.id);
                        }}
                        title="More options"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/>
                        </svg>
                      </button>
                      {openMenuId === proj.id && (
                        <div className={styles.menuPopover} onClick={(e) => e.stopPropagation()}>
                          <button 
                            type="button"
                            className={styles.menuOption} 
                            onClick={(e) => handleStartRename(proj, e)}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.menuOptionIcon}>
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                            <span>Rename</span>
                          </button>
                          <button 
                            type="button"
                            className={`${styles.menuOption} ${styles.deleteOption}`} 
                            onClick={(e) => handleDeleteProject(proj.id, e)}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.menuOptionIcon}>
                              <polyline points="3 6 5 6 21 6"/>
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                              <line x1="10" y1="11" x2="10" y2="17"/>
                              <line x1="14" y1="11" x2="14" y2="17"/>
                            </svg>
                            <span>Delete</span>
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Area */}
      <div className={styles.bottomArea} ref={profileRef}>
        {profileMenuOpen && (
          <div className={styles.profilePopover}>
            <div className={styles.popoverHeader}>
              {user?.avatar_url && !avatarError ? (
                <img
                  src={user.avatar_url}
                  alt=""
                  referrerPolicy="no-referrer"
                  className={styles.avatarImg}
                  onError={() => setAvatarError(true)}
                />
              ) : (
                <div
                  className={styles.avatarCircle}
                  style={{ backgroundColor: getAvatarColor(displayName) }}
                >
                  {initials}
                </div>
              )}
              <div className={styles.popoverHeaderInfo}>
                <span className={styles.popoverName}>{displayName}</span>
                <span className={styles.popoverEmail}>{user?.email || ''}</span>
              </div>
            </div>
            <button
              type="button"
              className={styles.popoverItem}
              onClick={() => {
                setProfileMenuOpen(false);
                handleNavClick('teams', 'openTeams');
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
              Team Workspace
            </button>
            <button
              type="button"
              className={styles.popoverItem}
              onClick={handleOpenSettings}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
              Settings
            </button>
            <button
              type="button"
              className={`${styles.popoverItem} ${styles.popoverItemLogout}`}
              onClick={handleLogout}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              Logout
            </button>
          </div>
        )}

        <div
          className={styles.userProfile}
          onClick={() => setProfileMenuOpen(!profileMenuOpen)}
          title="Account & Settings"
        >
          {user?.avatar_url && !avatarError ? (
            <img
              src={user.avatar_url}
              alt=""
              referrerPolicy="no-referrer"
              className={styles.avatarImg}
              onError={() => setAvatarError(true)}
            />
          ) : (
            <div
              className={styles.avatarCircle}
              style={{ backgroundColor: getAvatarColor(displayName) }}
            >
              {initials}
            </div>
          )}
          <div className={styles.userInfo}>
            <span className={styles.userName}>{displayName}</span>
            <span className={styles.userSubtext}>{user?.email || 'Settings'}</span>
          </div>
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`${styles.profileChevron} ${profileMenuOpen ? styles.profileChevronOpen : ''}`}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </div>

      <ConfirmModal
        isOpen={deleteChatConfirm.isOpen}
        title="Delete Chat"
        message="Are you sure you want to delete this chat?"
        confirmLabel="Delete"
        confirmDanger
        onConfirm={() => doDeleteProject(deleteChatConfirm.projectId)}
        onCancel={() => setDeleteChatConfirm({ isOpen: false, projectId: '', e: null })}
      />
    </aside>
  );
}
