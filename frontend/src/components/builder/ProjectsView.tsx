'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import styles from './ProjectsView.module.css';

interface ProjectsViewProps {
  onSelectProject?: (id: string) => void;
  onCreateProject?: () => void;
}

export default function ProjectsView({ onSelectProject, onCreateProject }: ProjectsViewProps) {
  const router = useRouter();
  const [projects, setProjects] = useState<any[]>([]);
  const [brands, setBrands] = useState<any[]>([]);
  const [brandsMap, setBrandsMap] = useState<Record<string, string>>({});
  const [activeMenuProjectId, setActiveMenuProjectId] = useState<string | null>(null);

  const handleCreateNewProject = () => {
    // Navigate to brand-setup with the new project flag
    router.push('/brand-setup?new=true');
  };

  const fetchProjects = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const token = localStorage.getItem('access_token');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${apiBase}/api/projects/`, { headers });
      const brandsRes = await fetch(`${apiBase}/api/brands/`, { headers });

      if (res.ok && brandsRes.ok) {
        const data = await res.json();
        const brandsData = await brandsRes.json();
        const bMap: Record<string, string> = {};
        brandsData.forEach((b: any) => { bMap[b.id] = b.brand_name; });
        setBrandsMap(bMap);
        setBrands(brandsData || []);
        setProjects(data || []);
      }
    } catch (e) {
      console.error("Failed to fetch projects", e);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  useEffect(() => {
    const closeMenu = () => setActiveMenuProjectId(null);
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  const handleRenameProject = async (id: string, currentTitle: string) => {
    const newTitle = prompt("Enter new project name:", currentTitle);
    if (!newTitle || !newTitle.trim()) return;

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const token = localStorage.getItem('access_token');
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${apiBase}/api/projects/${id}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({ title: newTitle.trim() })
      });
      if (res.ok) {
        setProjects(prev => prev.map(p => p.id === id ? { ...p, title: newTitle.trim() } : p));
      }
    } catch (e) {
      console.error("Failed to rename project", e);
    }
  };

  const handleDeleteProject = async (id: string) => {
    if (!confirm("Are you sure you want to delete this project and its research entirely?")) return;

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
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
      }
    } catch (e) {
      console.error("Failed to delete project", e);
    } finally {
      setActiveMenuProjectId(null);
    }
  };

  // Build unique brand cards so every onboarded brand gets 1 dedicated card
  const brandCards: any[] = brands.map((b: any) => {
    const latestProj = projects.find((p: any) => p.brand_config_id === b.id);
    return {
      id: latestProj ? latestProj.id : b.id,
      brand_config_id: b.id,
      title: b.brand_name,
      description: latestProj ? latestProj.title : (b.category || 'Strategic Intelligence'),
      created_at: b.created_at || (latestProj ? latestProj.created_at : new Date().toISOString()),
      agent_type: latestProj ? latestProj.agent_type : 'StratAI'
    };
  });

  projects.forEach((proj: any) => {
    if (proj.brand_config_id && !brandCards.some(c => c.brand_config_id === proj.brand_config_id)) {
      brandCards.push({
        id: proj.id,
        brand_config_id: proj.brand_config_id,
        title: brandsMap[proj.brand_config_id] || proj.title || 'Brand Project',
        description: proj.title,
        created_at: proj.created_at,
        agent_type: proj.agent_type
      });
    }
  });

  const displayProjects = brandCards.length > 0 ? brandCards : projects;

  const handleCardClick = (proj: any) => {
    if (proj.brand_config_id && typeof window !== 'undefined') {
      localStorage.setItem('brand_config_id', proj.brand_config_id);
    }
    window.dispatchEvent(new CustomEvent('projectChanged', { 
      detail: { projectId: proj.id, brand_config_id: proj.brand_config_id } 
    }));
    if (onSelectProject) {
      onSelectProject(proj.id);
    } else {
      window.dispatchEvent(new CustomEvent('openProject', { detail: { projectId: proj.id, brand_config_id: proj.brand_config_id } }));
    }
  };

  return (
    <div className={styles.wrapper}>
      {/* Top Header */}
      <div className={styles.header}>
        <h1 className={styles.welcomeTitle}>Welcome back!</h1>
        <div className={styles.actions}>
          <button type="button" className={styles.recentBtn}>Recent Updates</button>
          <button type="button" className={styles.createBtn} onClick={handleCreateNewProject}>
            Create New Project
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Most Used Section */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Most Used Agents</h2>
        <div className={styles.grid}>
          {displayProjects.map((proj, idx) => (
            <div 
              key={idx} 
              className={styles.card} 
              onClick={() => handleCardClick(proj)} 
              style={{ cursor: 'pointer', position: 'relative' }}
            >
              <div className={styles.cardHeader}>
                <div className={styles.agentAvatar}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                  </svg>
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
                        handleRenameProject(proj.id, proj.title);
                      }}
                      className={styles.optionsMenuItem}
                    >
                      Rename
                    </button>
                    <button 
                      type="button" 
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteProject(proj.id);
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
                </div>
                <div className={styles.metaInfo}>
                  {new Date(proj.created_at).toLocaleDateString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recently Chatted Section */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Agents You Recently Chatted With</h2>
        <div className={styles.grid}>
          {displayProjects.map((proj, idx) => (
            <div 
              key={idx} 
              className={styles.card} 
              onClick={() => handleCardClick(proj)} 
              style={{ cursor: 'pointer', position: 'relative' }}
            >
              <div className={styles.cardHeader}>
                <div className={styles.agentAvatar}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                  </svg>
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
                        handleRenameProject(proj.id, proj.title);
                      }}
                      className={styles.optionsMenuItem}
                    >
                      Rename
                    </button>
                    <button 
                      type="button" 
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteProject(proj.id);
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
                </div>
                <div className={styles.metaInfo}>
                  {new Date(proj.created_at).toLocaleDateString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
