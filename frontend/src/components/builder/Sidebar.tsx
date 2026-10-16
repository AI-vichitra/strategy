'use client';
import { useState, useEffect } from 'react';
import styles from './Sidebar.module.css';

interface Project {
  id: string;
  title: string;
  agent_type: string;
  created_at: string;
  brand_config_id: string;
}

export default function Sidebar() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [brands, setBrands] = useState<Record<string, string>>({});
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  // Close three dots popover on any outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest(`.${styles.menuBtn}`)) {
        return;
      }
      setOpenMenuId(null);
    };
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, []);

  const fetchProjects = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
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
        if (!data || data.length === 0) {
          window.location.href = '/brand-setup?new=true';
          return;
        }
        const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
        if (savedBrandId && data && data.length > 0) {
          const match = data.find((p: any) => p.brand_config_id === savedBrandId);
          if (match) {
            setActiveProjectId(match.id);
          } else if (!activeProjectId) {
            setActiveProjectId(data[0].id);
          }
        } else if (data && data.length > 0 && !activeProjectId) {
          setActiveProjectId(data[0].id);
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

  // Listen for project changes from MainContent
  useEffect(() => {
    const handleProjectChange = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail?.projectId) {
        setActiveProjectId(customEvent.detail.projectId);
        fetchProjects(); // refresh list
      }
    };
    
    const handleNewChat = () => {
      setActiveProjectId(null);
    };

    window.addEventListener('projectChanged', handleProjectChange);
    window.addEventListener('newChat', handleNewChat);
    return () => {
      window.removeEventListener('projectChanged', handleProjectChange);
      window.removeEventListener('newChat', handleNewChat);
    };
  }, []);

  const handleOpenProject = (projectId: string) => {
    setActiveProjectId(projectId);
    window.dispatchEvent(new CustomEvent('openProject', { detail: { projectId } }));
  };

  const handleDeleteProject = async (projectIdToDelete: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this chat?')) return;

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
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

  // Group all chat projects by date
  const groupedProjects = projects.reduce((groups: Record<string, Project[]>, proj) => {
    const date = new Date(proj.created_at);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
    let key = 'Older';
    if (diffDays === 0) key = 'Today';
    else if (diffDays === 1) key = 'Yesterday';
    else if (diffDays <= 7) key = 'This Week';
    else if (diffDays <= 30) key = 'This Month';
    if (!groups[key]) groups[key] = [];
    groups[key].push(proj);
    return groups;
  }, {});

  const groupOrder = ['Today', 'Yesterday', 'This Week', 'This Month', 'Older'];

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('brand_config_id');
    localStorage.removeItem('pathChosen');
    window.location.href = '/auth';
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
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('newChat')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
            Home
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openFiles')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 10V7l-5-5H6c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7"/>
              <path d="M14 2v4a2 2 0 0 0 2 2h4"/>
              <path d="M16 22h6"/><path d="M19 19v6"/>
            </svg>
            Files Generated
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openConnectorsView')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
            Connector
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openAgents')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7"/>
              <rect x="14" y="3" width="7" height="7"/>
              <rect x="14" y="14" width="7" height="7"/>
              <rect x="3" y="14" width="7" height="7"/>
            </svg>
            Agents
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openProjects')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            Projects
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openWorkflow')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            Workflow
          </a>
        </nav>

        {/* New Chat Button */}
        <button
          className={styles.newChatBtn}
          onClick={() => window.dispatchEvent(new CustomEvent('newChat'))}
          style={{ marginBottom: '16px' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          NEW CHAT
        </button>

        {/* Chat History */}
        <div className={styles.historySection}>
          <div className={styles.historyHeader}>Chat History</div>
          {loading ? (
            <div className={styles.historyEmpty}>Loading...</div>
          ) : projects.length === 0 ? (
            <div className={styles.historyEmpty}>No chats yet</div>
          ) : (
            groupOrder.map(group => {
              const items = groupedProjects[group];
              if (!items || items.length === 0) return null;
              return (
                <div key={group} className={styles.historyGroup}>
                  <div className={styles.historyGroupLabel}>{group}</div>
                  {items.map(proj => (
                    <div
                      key={proj.id}
                      className={`${styles.historyItemWrapper} ${proj.id === activeProjectId ? styles.historyItemActive : ''}`}
                      onClick={() => handleOpenProject(proj.id)}
                    >
                      <div className={styles.historyItemLeft}>
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.historyItemIcon}>
                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                        </svg>
                        <span className={styles.historyItemTitle}>
                          {proj.title}
                        </span>
                      </div>
                      
                      <div className={styles.menuContainer}>
                        <button 
                          className={styles.menuBtn} 
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenMenuId(openMenuId === proj.id ? null : proj.id);
                          }}
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/>
                          </svg>
                        </button>
                        {openMenuId === proj.id && (
                          <div className={styles.menuPopover}>
                            <button 
                              className={styles.deleteOption} 
                              onClick={(e) => handleDeleteProject(proj.id, e)}
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }}>
                                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>
                              </svg>
                              Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Bottom Area */}
      <div className={styles.bottomArea}>
        <div className={styles.userProfile}>
          <div className={styles.avatar}>AS</div>
          <div className={styles.userInfo}>
            <span className={styles.userName}>Apoorv Srivastava</span>
            <button className={styles.logoutBtn} onClick={handleLogout}>Logout</button>
          </div>
        </div>
      </div>
    </aside>
  );
}
