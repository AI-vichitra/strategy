'use client';

import React, { useState, useEffect, useCallback } from 'react';
import styles from './TeamsView.module.css';
import ConfirmModal from '../ConfirmModal';
import AlertModal from '../AlertModal';

interface TeamMember {
  id: string;
  team_id: string;
  user_id: string;
  role: string;
  full_name?: string | null;
  email: string;
  avatar_url?: string | null;
  joined_at?: string;
  allowed_brands?: string[] | null;
  allowed_projects?: string[] | null;
}

interface Team {
  id: string;
  name: string;
  description?: string | null;
  avatar_url?: string | null;
  admin_id: string;
  is_admin: boolean;
  role: string;
  members_count: number;
  members?: TeamMember[];
}

interface TeamProject {
  id: string;
  title: string;
  agent_type: string;
  description?: string | null;
  brand_config_id?: string | null;
  brand_name?: string;
  created_at?: string | null;
  team_id?: string | null;
  user_id: string;
  is_owner?: boolean;
}

interface AvailableProject {
  id: string;
  title: string;
  agent_type: string;
  brand_name?: string;
  created_at?: string | null;
}

interface InitialInvite {
  email: string;
  role: 'member' | 'admin';
}

interface TeamsViewProps {
  onBack?: () => void;
  onShowToast?: (msg: string) => void;
}

const GOOGLE_COLORS = [
  '#1a73e8', '#d93025', '#188038', '#f29900',
  '#a142f4', '#fa7b17', '#007b83', '#e52592'
];

function getAvatarColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return GOOGLE_COLORS[Math.abs(hash) % GOOGLE_COLORS.length];
}

function getInitials(name?: string | null, email?: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (email) return email.slice(0, 1).toUpperCase();
  return 'T';
}

function formatShortDate(dateStr?: string | null): string {
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
}

// ── Custom Styled Role Dropdown Component (User Request: Sleek SaaS dropdown) ──
function RoleSelectDropdown({
  value,
  onChange,
  disabled = false,
}: {
  value: 'member' | 'admin';
  onChange: (val: 'member' | 'admin') => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [open]);

  return (
    <div className={styles.customRoleSelectWrapper} ref={ref}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((prev) => !prev)}
        className={`${styles.customRoleSelectBtn} ${open ? styles.customRoleSelectBtnOpen : ''}`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span>{value === 'admin' ? 'Admin' : 'Member'}</span>
        <svg
          className={`${styles.customRoleChevron} ${open ? styles.customRoleChevronRotated : ''}`}
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className={styles.customRoleDropdownMenu} role="listbox">
          <button
            type="button"
            className={`${styles.customRoleOptionItem} ${value === 'member' ? styles.customRoleOptionActive : ''}`}
            onClick={() => {
              onChange('member');
              setOpen(false);
            }}
          >
            <div className={styles.customRoleOptionText}>
              <span className={styles.customRoleOptionTitle}>Member</span>
              <span className={styles.customRoleOptionDesc}>Can access assigned team projects and chats</span>
            </div>
            {value === 'member' && (
              <svg className={styles.customRoleCheckmark} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
          </button>
          <button
            type="button"
            className={`${styles.customRoleOptionItem} ${value === 'admin' ? styles.customRoleOptionActive : ''}`}
            onClick={() => {
              onChange('admin');
              setOpen(false);
            }}
          >
            <div className={styles.customRoleOptionText}>
              <span className={styles.customRoleOptionTitle}>Admin</span>
              <span className={styles.customRoleOptionDesc}>Can invite teammates and grant project access</span>
            </div>
            {value === 'admin' && (
              <svg className={styles.customRoleCheckmark} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

export default function TeamsView({ onBack, onShowToast }: TeamsViewProps) {
  // Navigation / View state: 'cards' | 'create' | 'detail'
  const [viewMode, setViewMode] = useState<'cards' | 'create' | 'detail'>('cards');

  const [teams, setTeams] = useState<Team[]>([]);
  const [activeTeam, setActiveTeam] = useState<Team | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUserEmail, setCurrentUserEmail] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [currentUserRole, setCurrentUserRole] = useState<string>('admin');

  // Team Projects
  const [teamProjects, setTeamProjects] = useState<TeamProject[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [availableProjects, setAvailableProjects] = useState<AvailableProject[]>([]);

  // Project Giving Modal (Admin only)
  const [giveProjectModalOpen, setGiveProjectModalOpen] = useState(false);
  const [selectedProjectIdToShare, setSelectedProjectIdToShare] = useState<string>('');
  const [sharingProject, setSharingProject] = useState(false);

  // Project Revoking Confirmation
  const [revokeProjectConfirm, setRevokeProjectConfirm] = useState<{
    isOpen: boolean;
    projectId: string;
    projectTitle: string;
  }>({ isOpen: false, projectId: '', projectTitle: '' });
  const [revokingProject, setRevokingProject] = useState(false);

  // Member Project Permissions Modal (Admin only)
  const [memberPermissionsModal, setMemberPermissionsModal] = useState<{
    isOpen: boolean;
    member: TeamMember | null;
    accessType: 'all' | 'custom';
    selectedProjectIds: string[];
  }>({
    isOpen: false,
    member: null,
    accessType: 'all',
    selectedProjectIds: [],
  });
  const [savingMemberPermissions, setSavingMemberPermissions] = useState(false);

  // Inline Detail Invite state
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'member' | 'admin'>('member');
  const [inviteProjectScope, setInviteProjectScope] = useState<'all' | 'custom'>('all');
  const [inviteSelectedProjects, setInviteSelectedProjects] = useState<string[]>([]);
  const [inviting, setInviting] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Create team state
  const [newTeamName, setNewTeamName] = useState('');
  const [newTeamDesc, setNewTeamDesc] = useState('');
  const [creating, setCreating] = useState(false);

  // Creation-time teammate invites list (User request!)
  const [creationInviteInput, setCreationInviteInput] = useState('');
  const [creationInviteRole, setCreationInviteRole] = useState<'member' | 'admin'>('member');
  const [creationInvites, setCreationInvites] = useState<InitialInvite[]>([]);

  // Removing member
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [removeConfirm, setRemoveConfirm] = useState<{ isOpen: boolean; memberId: string; memberEmail: string }>({
    isOpen: false,
    memberId: '',
    memberEmail: '',
  });

  // Delete team confirm
  const [deleteTeamConfirm, setDeleteTeamConfirm] = useState<{ isOpen: boolean; teamId: string; teamName: string }>({
    isOpen: false,
    teamId: '',
    teamName: '',
  });
  const [deletingTeam, setDeletingTeam] = useState(false);

  // Alert Modal & Toast
  const [alertModal, setAlertModal] = useState<{ isOpen: boolean; title?: string; message: string }>({
    isOpen: false,
    title: 'Notice',
    message: '',
  });
  const [localToast, setLocalToast] = useState<string | null>(null);

  // Active Filter state: 'all' | 'admins' | 'members' | 'projects' (User request: clickable badges work like filter)
  const [activeFilter, setActiveFilter] = useState<'all' | 'admins' | 'members' | 'projects'>('all');

  // In-place team editing state (User request: hover pencil icon & editable name/description)
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameEditVal, setNameEditVal] = useState('');
  const [isEditingDesc, setIsEditingDesc] = useState(false);
  const [descEditVal, setDescEditVal] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);

  const startEditName = () => {
    if (!activeTeam?.is_admin) return;
    setNameEditVal(activeTeam.name);
    setIsEditingName(true);
  };

  const cancelEditName = () => {
    setIsEditingName(false);
    setNameEditVal('');
  };

  const handleSaveTeamName = async () => {
    if (!activeTeam || !nameEditVal.trim() || savingEdit) return;
    setSavingEdit(true);
    try {
      const res = await fetch(`${apiBase}/api/teams/${activeTeam.id}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ name: nameEditVal.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to update workspace name');
      }
      const updated = await res.json();
      setActiveTeam((prev) => (prev ? { ...prev, name: updated.name } : null));
      setTeams((prev) =>
        prev.map((t) => (t.id === activeTeam.id ? { ...t, name: updated.name } : t))
      );
      setIsEditingName(false);
      showToast('Workspace name updated successfully');
    } catch (e: any) {
      showToast(e.message || 'Failed to update name');
    } finally {
      setSavingEdit(false);
    }
  };

  const startEditDesc = () => {
    if (!activeTeam?.is_admin) return;
    setDescEditVal(activeTeam.description || '');
    setIsEditingDesc(true);
  };

  const cancelEditDesc = () => {
    setIsEditingDesc(false);
    setDescEditVal('');
  };

  const handleSaveTeamDesc = async () => {
    if (!activeTeam || savingEdit) return;
    setSavingEdit(true);
    try {
      const res = await fetch(`${apiBase}/api/teams/${activeTeam.id}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ description: descEditVal.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to update workspace description');
      }
      const updated = await res.json();
      setActiveTeam((prev) => (prev ? { ...prev, description: updated.description } : null));
      setTeams((prev) =>
        prev.map((t) => (t.id === activeTeam.id ? { ...t, description: updated.description } : t))
      );
      setIsEditingDesc(false);
      showToast('Workspace description updated successfully');
    } catch (e: any) {
      showToast(e.message || 'Failed to update description');
    } finally {
      setSavingEdit(false);
    }
  };

  // ── Team Logo / Avatar Upload State & Handlers (User Request) ─────────────
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const logoInputRef = React.useRef<HTMLInputElement>(null);

  const handleLogoFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeTeam) return;

    if (file.size > 5 * 1024 * 1024) {
      setAlertModal({
        isOpen: true,
        title: 'File Too Large',
        message: 'Logo image must be smaller than 5MB.',
      });
      return;
    }

    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const res = await fetch(`${apiBase}/api/teams/${activeTeam.id}/avatar`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to upload workspace logo');
      }

      const updated: Team = await res.json();
      setActiveTeam((prev) => (prev ? { ...prev, avatar_url: updated.avatar_url } : null));
      setTeams((prev) =>
        prev.map((t) => (t.id === activeTeam.id ? { ...t, avatar_url: updated.avatar_url } : t))
      );
      showToast('Workspace logo updated successfully!');
    } catch (err: any) {
      showToast(err.message || 'Error uploading logo');
    } finally {
      setUploadingLogo(false);
      if (logoInputRef.current) {
        logoInputRef.current.value = '';
      }
    }
  };

  const handleRemoveLogo = async () => {
    if (!activeTeam || uploadingLogo) return;
    setUploadingLogo(true);
    try {
      const res = await fetch(`${apiBase}/api/teams/${activeTeam.id}/avatar`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to remove logo');
      }
      setActiveTeam((prev) => (prev ? { ...prev, avatar_url: null } : null));
      setTeams((prev) =>
        prev.map((t) => (t.id === activeTeam.id ? { ...t, avatar_url: null } : t))
      );
      showToast('Workspace logo removed.');
    } catch (err: any) {
      showToast(err.message || 'Error removing logo');
    } finally {
      setUploadingLogo(false);
    }
  };

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const showToast = useCallback((msg: string) => {
    if (onShowToast) onShowToast(msg);
    setLocalToast(msg);
    setTimeout(() => setLocalToast(null), 3500);
  }, [onShowToast]);

  const getAuthHeaders = (): Record<string, string> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    return token
      ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
      : { 'Content-Type': 'application/json' };
  };

  // Fetch projects belonging to active team
  const loadTeamProjects = async (teamId: string) => {
    setLoadingProjects(true);
    try {
      const res = await fetch(`${apiBase}/api/teams/${teamId}/projects`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setTeamProjects(data);
      }
    } catch (e) {
      console.error('Failed to load team projects:', e);
    } finally {
      setLoadingProjects(false);
    }
  };

  // Fetch personal projects available to be added to this team
  const loadAvailableProjects = async (teamId: string) => {
    try {
      const res = await fetch(`${apiBase}/api/teams/${teamId}/available-projects`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setAvailableProjects(data);
        if (data.length > 0 && !selectedProjectIdToShare) {
          setSelectedProjectIdToShare(data[0].id);
        }
      }
    } catch (e) {
      console.error('Failed to load available projects:', e);
    }
  };

  const loadTeamDetails = async (teamId: string) => {
    setIsEditingName(false);
    setIsEditingDesc(false);
    try {
      const res = await fetch(`${apiBase}/api/teams/${teamId}`, { headers: getAuthHeaders() });
      if (res.ok) {
        const details: Team = await res.json();
        setActiveTeam(details);
        await loadTeamProjects(details.id);
        if (details.is_admin) {
          await loadAvailableProjects(details.id);
        }
      }
    } catch (e) {
      console.error('Failed to load team details:', e);
    }
  };

  const fetchTeams = async (preferredTeamId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/api/teams`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data: Team[] = await res.json();
        setTeams(data);
        if (data.length > 0) {
          const target = preferredTeamId
            ? data.find((t) => t.id === preferredTeamId) || data[0]
            : activeTeam
            ? data.find((t) => t.id === activeTeam.id) || data[0]
            : data[0];
          setActiveTeam(target);
          await loadTeamDetails(target.id);
          // If teams exist, display detail if preferredTeamId was specified, otherwise maintain detail or show cards
          setViewMode((curr) => (preferredTeamId ? 'detail' : curr === 'detail' ? 'detail' : 'cards'));
        } else {
          setActiveTeam(null);
          // No teams exist -> open creation screen directly as requested
          setViewMode('create');
        }
      } else {
        setError('Failed to load teams');
      }
    } catch (e) {
      console.error('Error fetching teams:', e);
      setError('Network error while loading teams');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${apiBase}/api/auth/me`, { headers: getAuthHeaders() });
        if (res.ok) {
          const data = await res.json();
          if (data?.email) setCurrentUserEmail(data.email);
          if (data?.id) setCurrentUserId(data.id);
          if (data?.role) setCurrentUserRole(data.role);
        }
      } catch {
        // non-critical
      }
      fetchTeams();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Open Specific Team Detail ─────────────────────────────────────────────
  const handleOpenTeamDetail = async (team: Team, initialFilter: 'all' | 'admins' | 'members' | 'projects' = 'all') => {
    setActiveTeam(team);
    setActiveFilter(initialFilter);
    setIsEditingName(false);
    setIsEditingDesc(false);
    await loadTeamDetails(team.id);
    setViewMode('detail');
  };

  // ── Add Teammate to Creation List ─────────────────────────────────────────
  const handleAddCreationInvite = () => {
    const email = creationInviteInput.trim().toLowerCase();
    if (!email) return;

    if (!email.includes('@') || !email.includes('.')) {
      setAlertModal({
        isOpen: true,
        title: 'Invalid Email',
        message: 'Please enter a valid email address.',
      });
      return;
    }

    if (creationInvites.some((inv) => inv.email === email) || email === currentUserEmail?.toLowerCase()) {
      setAlertModal({
        isOpen: true,
        title: 'Duplicate Email',
        message: 'This email is already added or belongs to you.',
      });
      return;
    }

    setCreationInvites((prev) => [...prev, { email, role: creationInviteRole }]);
    setCreationInviteInput('');
  };

  const handleRemoveCreationInvite = (emailToRemove: string) => {
    setCreationInvites((prev) => prev.filter((inv) => inv.email !== emailToRemove));
  };

  // ── Create Team With Optional Teammate Invites ────────────────────────────
  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeamName.trim()) return;

    if (currentUserRole === 'member') {
      setAlertModal({
        isOpen: true,
        title: 'Admin Privileges Required',
        message: 'You need admin privileges to create a new team workspace.',
      });
      return;
    }

    // Include any email typed in the invite box that wasn't explicitly "+ Add"-ed
    let finalInvites = [...creationInvites];
    const pendingTypedEmail = creationInviteInput.trim().toLowerCase();
    if (
      pendingTypedEmail &&
      pendingTypedEmail.includes('@') &&
      !finalInvites.some((inv) => inv.email === pendingTypedEmail) &&
      pendingTypedEmail !== currentUserEmail?.toLowerCase()
    ) {
      finalInvites.push({ email: pendingTypedEmail, role: creationInviteRole });
    }

    setCreating(true);
    try {
      const payload: Record<string, any> = {
        name: newTeamName.trim(),
        description: newTeamDesc.trim() || null,
      };

      if (finalInvites.length > 0) {
        payload.initial_invites = finalInvites.map((inv) => ({
          email: inv.email,
          role: inv.role,
        }));
      }

      const res = await fetch(`${apiBase}/api/teams`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const created: Team = await res.json();
        setNewTeamName('');
        setNewTeamDesc('');
        setCreationInvites([]);
        setCreationInviteInput('');

        const msg = finalInvites.length > 0
          ? `Team "${created.name}" created and ${finalInvites.length} invitation(s) sent!`
          : `Team "${created.name}" created!`;
        showToast(msg);

        // Switch to the newly created team workspace detail view
        await fetchTeams(created.id);
        setViewMode('detail');
      } else {
        const err = await res.json().catch(() => ({}));
        setAlertModal({
          isOpen: true,
          title: 'Cannot Create Team',
          message: err.detail || 'Could not create team workspace. Admin privileges are required.',
        });
      }
    } catch {
      setAlertModal({
        isOpen: true,
        title: 'Error',
        message: 'Failed to create team. Please try again.',
      });
    } finally {
      setCreating(false);
    }
  };

  // ── Delete Team ───────────────────────────────────────────────────────────
  const handleDeleteTeam = (teamId: string, teamName: string) => {
    setDeleteTeamConfirm({ isOpen: true, teamId, teamName });
  };

  const doDeleteTeam = async () => {
    if (!deleteTeamConfirm.teamId) return;
    setDeletingTeam(true);
    try {
      const res = await fetch(`${apiBase}/api/teams/${deleteTeamConfirm.teamId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        setDeleteTeamConfirm({ isOpen: false, teamId: '', teamName: '' });
        showToast(`Team workspace "${deleteTeamConfirm.teamName}" deleted.`);
        await fetchTeams();
        setViewMode('cards');
      } else {
        const err = await res.json().catch(() => ({}));
        setAlertModal({
          isOpen: true,
          title: 'Error',
          message: err.detail || 'Failed to delete team.',
        });
      }
    } catch {
      setAlertModal({
        isOpen: true,
        title: 'Error',
        message: 'Network error while deleting team.',
      });
    } finally {
      setDeletingTeam(false);
    }
  };

  // ── Give Project Access to Team ───────────────────────────────────────────
  const handleGiveProjectAccess = async () => {
    if (!activeTeam || !selectedProjectIdToShare) return;
    setSharingProject(true);
    try {
      const res = await fetch(`${apiBase}/api/teams/${activeTeam.id}/projects/${selectedProjectIdToShare}`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (res.ok) {
        setGiveProjectModalOpen(false);
        showToast(data.message || 'Project shared with team workspace!');
        await loadTeamProjects(activeTeam.id);
        await loadAvailableProjects(activeTeam.id);
      } else {
        setAlertModal({
          isOpen: true,
          title: 'Permission Denied',
          message: data.detail || 'Failed to share project with team.',
        });
      }
    } catch {
      setAlertModal({
        isOpen: true,
        title: 'Error',
        message: 'Network error while assigning project to team.',
      });
    } finally {
      setSharingProject(false);
    }
  };

  // ── Revoke Project Access from Team ───────────────────────────────────────
  const confirmRevokeProject = (projectId: string, projectTitle: string) => {
    setRevokeProjectConfirm({ isOpen: true, projectId, projectTitle });
  };

  const doRevokeProject = async () => {
    if (!activeTeam || !revokeProjectConfirm.projectId) return;
    setRevokingProject(true);
    try {
      const res = await fetch(
        `${apiBase}/api/teams/${activeTeam.id}/projects/${revokeProjectConfirm.projectId}`,
        {
          method: 'DELETE',
          headers: getAuthHeaders(),
        }
      );
      if (res.ok) {
        setRevokeProjectConfirm({ isOpen: false, projectId: '', projectTitle: '' });
        showToast(`Project "${revokeProjectConfirm.projectTitle}" access revoked from team.`);
        await loadTeamProjects(activeTeam.id);
        await loadAvailableProjects(activeTeam.id);
      } else {
        const err = await res.json().catch(() => ({}));
        setAlertModal({
          isOpen: true,
          title: 'Error',
          message: err.detail || 'Could not revoke project access.',
        });
      }
    } catch {
      setAlertModal({
        isOpen: true,
        title: 'Error',
        message: 'Network error while revoking project access.',
      });
    } finally {
      setRevokingProject(false);
    }
  };

  // ── Manage Member Project Access ──────────────────────────────────────────
  const openMemberPermissions = (member: TeamMember) => {
    if (activeTeam?.id) {
      loadAvailableProjects(activeTeam.id);
    }
    const isCustom = Array.isArray(member.allowed_projects) && member.allowed_projects.length > 0;
    setMemberPermissionsModal({
      isOpen: true,
      member,
      accessType: isCustom ? 'custom' : 'all',
      selectedProjectIds: member.allowed_projects ? [...member.allowed_projects] : [],
    });
  };

  const saveMemberPermissions = async () => {
    if (!activeTeam || !memberPermissionsModal.member) return;
    setSavingMemberPermissions(true);
    try {
      // If custom access, check if any selected projects are in availableProjects (admin projects not yet in team)
      if (memberPermissionsModal.accessType === 'custom') {
        const toPush = availableProjects.filter((p) =>
          memberPermissionsModal.selectedProjectIds.includes(p.id)
        );
        for (const p of toPush) {
          try {
            await fetch(`${apiBase}/api/teams/${activeTeam.id}/projects/${p.id}`, {
              method: 'POST',
              headers: getAuthHeaders(),
            });
          } catch (pushErr) {
            console.warn(`Failed to push project ${p.id} to team:`, pushErr);
          }
        }
      }

      const payload = {
        allowed_projects:
          memberPermissionsModal.accessType === 'all'
            ? null
            : memberPermissionsModal.selectedProjectIds,
      };

      const res = await fetch(
        `${apiBase}/api/teams/${activeTeam.id}/members/${memberPermissionsModal.member.user_id}/projects`,
        {
          method: 'PATCH',
          headers: getAuthHeaders(),
          body: JSON.stringify(payload),
        }
      );
      if (res.ok) {
        setMemberPermissionsModal((prev) => ({ ...prev, isOpen: false }));
        showToast(`Updated project access for ${memberPermissionsModal.member.email}!`);
        await loadTeamDetails(activeTeam.id);
      } else {
        const err = await res.json().catch(() => ({}));
        setAlertModal({
          isOpen: true,
          title: 'Error',
          message: err.detail || 'Could not update project access.',
        });
      }
    } catch {
      setAlertModal({
        isOpen: true,
        title: 'Error',
        message: 'Failed to update member project permissions.',
      });
    } finally {
      setSavingMemberPermissions(false);
    }
  };

  // ── Invite Member (from Detail View) ──────────────────────────────────────
  const handleInviteMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTeam || !inviteEmail.trim()) return;

    if (!activeTeam.is_admin) {
      setAlertModal({
        isOpen: true,
        title: 'Admin Privileges Required',
        message: 'You need admin privileges to invite teammates to this workspace.',
      });
      return;
    }

    setInviting(true);
    setFeedback(null);
    try {
      const payload: Record<string, any> = {
        email: inviteEmail.trim().toLowerCase(),
        role: inviteRole,
        team_id: activeTeam.id,
      };

      if (inviteProjectScope === 'custom') {
        payload.allowed_projects = inviteSelectedProjects;
        // Push any selected admin projects to this team
        const toPush = availableProjects.filter((p) =>
          inviteSelectedProjects.includes(p.id)
        );
        for (const p of toPush) {
          try {
            await fetch(`${apiBase}/api/teams/${activeTeam.id}/projects/${p.id}`, {
              method: 'POST',
              headers: getAuthHeaders(),
            });
          } catch (pushErr) {
            console.warn(`Failed to push project ${p.id} to team:`, pushErr);
          }
        }
      } else {
        payload.allowed_projects = null;
      }

      const res = await fetch(`${apiBase}/api/teams/${activeTeam.id}/invite`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok) {
        setInviteEmail('');
        setInviteProjectScope('all');
        setInviteSelectedProjects([]);
        setFeedback({
          type: 'success',
          message: data.already_registered
            ? `${data.message} They now have full access.`
            : `Invitation sent successfully! Link is valid for 7 days.`,
        });
        showToast('Teammate invited successfully!');
        await loadTeamDetails(activeTeam.id);
      } else {
        setFeedback({ type: 'error', message: data.detail || 'Failed to send invitation.' });
      }
    } catch {
      setFeedback({ type: 'error', message: 'Network error while sending invitation.' });
    } finally {
      setInviting(false);
    }
  };

  // ── Remove Member ─────────────────────────────────────────────────────────
  const handleRemoveMember = (memberId: string, memberEmail: string) => {
    if (!activeTeam) return;
    setRemoveConfirm({ isOpen: true, memberId, memberEmail });
  };

  const doRemoveMember = async (memberId: string, memberEmail: string) => {
    setRemoveConfirm({ isOpen: false, memberId: '', memberEmail: '' });
    if (!activeTeam) return;
    setRemovingId(memberId);
    try {
      const res = await fetch(`${apiBase}/api/teams/${activeTeam.id}/members/${memberId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        showToast(`${memberEmail} removed from team.`);
        await loadTeamDetails(activeTeam.id);
      } else {
        const err = await res.json().catch(() => ({}));
        setAlertModal({ isOpen: true, title: 'Error', message: err.detail || 'Could not remove member.' });
      }
    } catch (e) {
      console.error('Failed to remove member:', e);
    } finally {
      setRemovingId(null);
    }
  };

  const isUserTeamAdmin = activeTeam ? activeTeam.is_admin : currentUserRole !== 'member';

  return (
    <div className={styles.wrapper}>
      {/* Top Back Button */}
      {viewMode === 'detail' ? (
        <button
          type="button"
          className={styles.backBtn}
          onClick={() => setViewMode('cards')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Back to Workspaces
        </button>
      ) : viewMode === 'create' && teams.length > 0 ? (
        <button
          type="button"
          className={styles.backBtn}
          onClick={() => setViewMode('cards')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Back to Workspaces
        </button>
      ) : onBack ? (
        <button type="button" className={styles.backBtn} onClick={onBack}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Back to Studio
        </button>
      ) : null}

      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.iconBox}>
            {viewMode === 'detail' && activeTeam?.avatar_url ? (
              <img
                src={
                  activeTeam.avatar_url.startsWith('http') || activeTeam.avatar_url.startsWith('data:')
                    ? activeTeam.avatar_url
                    : `${apiBase}${activeTeam.avatar_url}`
                }
                alt=""
                style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '10px' }}
              />
            ) : (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            )}
          </div>
          <div>
            <h1 className={styles.title}>
              {viewMode === 'detail' && activeTeam ? activeTeam.name : 'Team Workspace'}
            </h1>
            <p className={styles.subtitle}>
              {viewMode === 'detail' && activeTeam
                ? activeTeam.description || 'Collaborate, share strategic projects, and manage team member access'
                : 'Collaborate, share strategic projects, and manage team member access'}
            </p>
          </div>
        </div>

        {/* Top-Right Create Team / Workspace Button */}
        <div className={styles.headerActions}>
          {viewMode === 'cards' && (
            isUserTeamAdmin ? (
              <button
                type="button"
                className={styles.btnPrimary}
                onClick={() => setViewMode('create')}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                Create Workspace
              </button>
            ) : (
              <button
                type="button"
                className={`${styles.btnSecondary} ${styles.newTeamBtnDisabled}`}
                title="You need admin privileges to create a new team workspace"
                onClick={() =>
                  setAlertModal({
                    isOpen: true,
                    title: 'Admin Privileges Required',
                    message: 'You need admin privileges to create a new team workspace. Please ask your administrator.',
                  })
                }
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                Create Workspace
              </button>
            )
          )}

          {viewMode === 'detail' && (
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={() => setViewMode('cards')}
            >
              All Workspaces
            </button>
          )}
        </div>
      </div>

      {/* ── Non-Admin Notice Banner (In Detail Mode) ──────────────────── */}
      {viewMode === 'detail' && activeTeam && !activeTeam.is_admin && (
        <div className={styles.memberNoticeBanner}>
          <div className={styles.memberNoticeIcon}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <div>
            <strong>Member Workspace Access:</strong> You are viewing this workspace as a team member. You need admin privileges to invite teammates, create workspaces, or manage project permissions.
          </div>
        </div>
      )}

      {/* ── Main Window Content Area ─────────────────────────────────── */}
      <div className={viewMode === 'cards' && teams.length > 0 ? styles.cardsContainer : styles.card}>
        {loading ? (
          <div className={styles.stateBox}>
            <p>Loading team workspaces...</p>
          </div>
        ) : error ? (
          <div className={styles.stateBox}>
            <p className={styles.errorText}>{error}</p>
            <button type="button" className={styles.btnPrimary} onClick={() => fetchTeams()}>
              Retry
            </button>
          </div>
        ) : viewMode === 'cards' && teams.length > 0 ? (
          /* ══════════════════════════════════════════════════════════════
             STATE 1: TEAM CARDS GRID VIEW (When teams exist)
             ══════════════════════════════════════════════════════════════ */
          <div>
            <div className={styles.sectionHeader}>
              <div className={styles.sectionTitle}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="7" height="7" />
                  <rect x="14" y="3" width="7" height="7" />
                  <rect x="14" y="14" width="7" height="7" />
                  <rect x="3" y="14" width="7" height="7" />
                </svg>
                Your Team Workspaces
                <span className={styles.sectionCounter}>{teams.length}</span>
              </div>
            </div>

            <div className={styles.teamsCardsGrid}>
              {teams.map((team) => (
                <div
                  key={team.id}
                  className={styles.teamCardItem}
                  onClick={() => handleOpenTeamDetail(team)}
                >
                  <div className={styles.teamCardItemHeader}>
                    <div className={styles.teamCardHeaderLeft}>
                      <div className={styles.teamCardAvatar}>
                        {team.avatar_url ? (
                          <img
                            src={
                              team.avatar_url.startsWith('http') || team.avatar_url.startsWith('data:')
                                ? team.avatar_url
                                : `${apiBase}${team.avatar_url}`
                            }
                            alt=""
                            style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '10px' }}
                          />
                        ) : (
                          (team.name || 'T').charAt(0).toUpperCase()
                        )}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <h4 className={styles.teamCardName} title={team.name}>
                          {team.name}
                        </h4>
                      </div>
                    </div>
                    <span
                      className={`${styles.roleBadge} ${
                        team.is_admin ? styles.badgeAdmin : styles.badgeMember
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenTeamDetail(team, 'admins');
                      }}
                      title="Open workspace filtered by Administrators"
                    >
                      {team.is_admin ? 'Admin' : 'Member'}
                    </span>
                  </div>

                  <p className={styles.teamCardDesc}>
                    {team.description || 'Collaborative strategy workspace for your organization.'}
                  </p>

                  <div className={styles.teamCardFooter}>
                    <div
                      className={styles.teamCardMembers}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenTeamDetail(team, 'members');
                      }}
                      title="Open workspace filtered by Members"
                      style={{ cursor: 'pointer' }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                        <circle cx="9" cy="7" r="4" />
                      </svg>
                      {team.members_count || 1} Member{team.members_count !== 1 ? 's' : ''}
                    </div>

                    <div className={styles.teamCardActions}>
                      <button
                        type="button"
                        className={styles.btnSecondary}
                        style={{ padding: '5px 12px', fontSize: '12px' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenTeamDetail(team);
                        }}
                      >
                        Manage →
                      </button>

                      {team.is_admin && (
                        <button
                          type="button"
                          className={styles.removeBtn}
                          title="Delete team workspace"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteTeam(team.id, team.name);
                          }}
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}

              {/* Extra Dashed Card for "+ Create Workspace" */}
              {isUserTeamAdmin && (
                <div
                  className={styles.teamCardCreate}
                  onClick={() => setViewMode('create')}
                >
                  <div className={styles.teamCardCreateIcon}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                  </div>
                  <h4 className={styles.teamCardCreateTitle}>Create New Workspace</h4>
                  <p className={styles.teamCardCreateDesc}>
                    Add another collaborative team workspace and invite colleagues.
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : viewMode === 'create' || teams.length === 0 ? (
          /* ══════════════════════════════════════════════════════════════
             STATE 2: CREATE TEAM WORKSPACE PAGE WITH INLINE INVITE FIELD
             ══════════════════════════════════════════════════════════════ */
          <div className={styles.createBox}>
            <div className={styles.createHeader}>
              <h3>Create a New Team Workspace</h3>
              {teams.length > 0 && (
                <button
                  type="button"
                  onClick={() => setViewMode('cards')}
                  className={styles.cancelLink}
                >
                  Cancel
                </button>
              )}
            </div>

            {currentUserRole === 'member' ? (
              <div className={styles.stateBox} style={{ padding: '24px 0' }}>
                <div className={styles.stateIcon}>
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                </div>
                <h4 className={styles.stateTitle}>Admin Privileges Required</h4>
                <p className={styles.stateDesc}>
                  You need admin privileges to create a new team workspace. Please ask your organization administrator to create a workspace and invite you.
                </p>
                {teams.length > 0 && (
                  <button type="button" className={styles.btnSecondary} onClick={() => setViewMode('cards')}>
                    Return to Workspaces
                  </button>
                )}
              </div>
            ) : (
              <>
                <p className={styles.createDesc}>
                  Group your strategy reports, competitor audits, and collaborate with your colleagues in a shared workspace.
                </p>
                <form onSubmit={handleCreateTeam} className={styles.createForm}>
                  {/* Team Name */}
                  <div>
                    <label style={{ display: 'block', fontSize: '12.5px', fontWeight: 600, color: '#1A1A1A', marginBottom: '6px' }}>
                      Team Name *
                    </label>
                    <input
                      type="text"
                      placeholder="Team Name (e.g. Growth Marketing, Apex Strategy)"
                      value={newTeamName}
                      onChange={(e) => setNewTeamName(e.target.value)}
                      className={styles.inputField}
                      style={{ width: '100%', boxSizing: 'border-box' }}
                      required
                    />
                  </div>

                  {/* Team Description */}
                  <div>
                    <label style={{ display: 'block', fontSize: '12.5px', fontWeight: 600, color: '#1A1A1A', marginBottom: '6px' }}>
                      Description (Optional)
                    </label>
                    <input
                      type="text"
                      placeholder="Describe the workspace focus or department"
                      value={newTeamDesc}
                      onChange={(e) => setNewTeamDesc(e.target.value)}
                      className={styles.inputField}
                      style={{ width: '100%', boxSizing: 'border-box' }}
                    />
                  </div>

                  {/* ── Teammates Invite Field at Creation Time (User Request) ── */}
                  <div className={styles.creationInvitesBox}>
                    <div className={styles.creationInvitesHeader}>
                      <h4 className={styles.creationInvitesTitle}>
                        Invite Teammates at Creation (Optional)
                      </h4>
                      <p className={styles.creationInvitesDesc}>
                        Enter colleague emails to automatically send workspace invitations when this team is created.
                      </p>
                    </div>

                    <div className={styles.creationInvitesRow}>
                      <input
                        type="email"
                        placeholder="colleague@company.com"
                        value={creationInviteInput}
                        onChange={(e) => setCreationInviteInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleAddCreationInvite();
                          }
                        }}
                        className={styles.inputEmail}
                      />
                      <RoleSelectDropdown
                        value={creationInviteRole}
                        onChange={(val) => setCreationInviteRole(val)}
                      />
                      <button
                        type="button"
                        className={styles.btnSecondary}
                        onClick={handleAddCreationInvite}
                      >
                        + Add Teammate
                      </button>
                    </div>

                    {/* Added Teammate Chips */}
                    {creationInvites.length > 0 && (
                      <div className={styles.inviteChipList}>
                        {creationInvites.map((inv) => (
                          <div key={inv.email} className={styles.inviteChip}>
                            <span>{inv.email}</span>
                            <span className={styles.inviteChipRole}>{inv.role}</span>
                            <button
                              type="button"
                              className={styles.chipRemoveBtn}
                              onClick={() => handleRemoveCreationInvite(inv.email)}
                              title="Remove"
                            >
                              ✕
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                    <button
                      type="submit"
                      disabled={creating || !newTeamName.trim()}
                      className={styles.btnPrimary}
                    >
                      {creating
                        ? 'Creating Workspace & Inviting...'
                        : creationInvites.length > 0
                        ? `Create Workspace & Send ${creationInvites.length} Invite${creationInvites.length > 1 ? 's' : ''}`
                        : 'Create Workspace'}
                    </button>
                    {teams.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setViewMode('cards')}
                        className={styles.btnSecondary}
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </form>
              </>
            )}
          </div>
        ) : viewMode === 'detail' && activeTeam ? (
          /* ══════════════════════════════════════════════════════════════
             STATE 3: DETAILED TEAM WORKSPACE VIEW (Projects & Members)
             ══════════════════════════════════════════════════════════════ */
          <div className={styles.body}>
            {/* Team Switcher Header */}
            <div className={styles.teamSelectorRow}>
              <div className={styles.teamSelectWrapper}>
                <span className={styles.teamSelectLabel}>Active Workspace:</span>
                {teams.length > 1 ? (
                  <select
                    className={styles.teamSelect}
                    value={activeTeam.id}
                    onChange={(e) => loadTeamDetails(e.target.value)}
                  >
                    {teams.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.members_count || 1} members)
                      </option>
                    ))}
                  </select>
                ) : (
                  <span style={{ fontSize: '14px', fontWeight: 700, color: '#1A1A1A' }}>
                    {activeTeam.name}
                  </span>
                )}
              </div>

              <div className={styles.badgeGroup}>
                <button
                  type="button"
                  className={`${styles.roleBadge} ${
                    activeTeam.is_admin ? styles.badgeAdmin : styles.badgeMember
                  } ${activeFilter === 'admins' ? styles.filterBadgeActive : ''}`}
                  onClick={() => setActiveFilter((curr) => (curr === 'admins' ? 'all' : 'admins'))}
                  title="Filter by Team Administrators"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                  Admin
                </button>
                <button
                  type="button"
                  className={`${styles.countBadge} ${
                    activeFilter === 'members' ? styles.filterBadgeActive : ''
                  }`}
                  onClick={() => setActiveFilter((curr) => (curr === 'members' ? 'all' : 'members'))}
                  title="Filter to view Team Members"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                  </svg>
                  {activeTeam.members?.length || activeTeam.members_count || 1} Members
                </button>
                <button
                  type="button"
                  className={`${styles.countBadge} ${
                    activeFilter === 'projects' ? styles.filterBadgeActive : ''
                  }`}
                  onClick={() => setActiveFilter((curr) => (curr === 'projects' ? 'all' : 'projects'))}
                  title="Filter to view Team Projects"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                  {teamProjects.length} Projects
                </button>
              </div>
            </div>

            {/* Filter Reset Banner (When any filter is active) */}
            {activeFilter !== 'all' && (
              <div className={styles.filterResetBanner}>
                <span>
                  Filtering view by:{' '}
                  <strong>
                    {activeFilter === 'admins'
                      ? 'Team Administrators only'
                      : activeFilter === 'members'
                      ? 'All Team Members'
                      : 'Team Projects only'}
                  </strong>
                </span>
                <button
                  type="button"
                  className={styles.filterResetBtn}
                  onClick={() => setActiveFilter('all')}
                >
                  Clear filter (Show All)
                </button>
              </div>
            )}

            {/* Team Profile Banner with Logo Upload & In-Place Editing (User Request) */}
            <div className={styles.teamCard}>
              <div className={styles.teamProfileContainer}>
                {/* Team Logo / Avatar with Local Upload (User Request) */}
                <div className={styles.teamAvatarCol}>
                  <div
                    className={`${styles.teamLogoWrapper} ${activeTeam.is_admin ? styles.teamLogoWrapperAdmin : ''}`}
                    onClick={() => {
                      if (activeTeam.is_admin && !uploadingLogo) {
                        logoInputRef.current?.click();
                      }
                    }}
                    title={activeTeam.is_admin ? 'Click to upload workspace logo from your computer' : activeTeam.name}
                  >
                    {activeTeam.avatar_url ? (
                      <img
                        src={
                          activeTeam.avatar_url.startsWith('http') || activeTeam.avatar_url.startsWith('data:')
                            ? activeTeam.avatar_url
                            : `${apiBase}${activeTeam.avatar_url}`
                        }
                        alt={activeTeam.name}
                        className={styles.teamLogoImg}
                      />
                    ) : (
                      <div className={styles.teamLogoFallback}>
                        {(activeTeam.name || 'T').charAt(0).toUpperCase()}
                      </div>
                    )}
                    {activeTeam.is_admin && (
                      <div className={styles.teamLogoOverlay}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                          <circle cx="12" cy="13" r="4" />
                        </svg>
                        <span>{uploadingLogo ? '...' : 'Upload'}</span>
                      </div>
                    )}
                  </div>
                  <input
                    type="file"
                    ref={logoInputRef}
                    style={{ display: 'none' }}
                    accept="image/png, image/jpeg, image/jpg, image/webp, image/svg+xml, image/gif"
                    onChange={handleLogoFileChange}
                  />
                  {activeTeam.is_admin && (
                    <div className={styles.avatarActionsRow}>
                      <button
                        type="button"
                        className={styles.uploadLogoBtnText}
                        onClick={() => logoInputRef.current?.click()}
                        disabled={uploadingLogo}
                      >
                        {uploadingLogo ? 'Uploading...' : activeTeam.avatar_url ? 'Change Logo' : '+ Upload Logo'}
                      </button>
                      {activeTeam.avatar_url && (
                        <button
                          type="button"
                          className={styles.removeLogoBtnText}
                          onClick={handleRemoveLogo}
                          disabled={uploadingLogo}
                          title="Remove workspace logo"
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  )}
                </div>

                <div className={styles.teamCardInfo} style={{ flex: 1, minWidth: 0 }}>
                {/* Team Name */}
                {isEditingName ? (
                  <div className={styles.inlineEditRow} style={{ marginBottom: '8px' }}>
                    <input
                      type="text"
                      className={styles.inlineEditInput}
                      value={nameEditVal}
                      onChange={(e) => setNameEditVal(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleSaveTeamName();
                        } else if (e.key === 'Escape') {
                          cancelEditName();
                        }
                      }}
                      autoFocus
                      disabled={savingEdit}
                    />
                    <button
                      type="button"
                      className={styles.inlineSaveBtn}
                      onClick={handleSaveTeamName}
                      disabled={savingEdit || !nameEditVal.trim()}
                      title="Save name (Enter)"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      className={styles.inlineCancelBtn}
                      onClick={cancelEditName}
                      disabled={savingEdit}
                      title="Cancel (Esc)"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                ) : (
                  <div
                    className={activeTeam.is_admin ? styles.editableWrapper : undefined}
                    onClick={activeTeam.is_admin ? startEditName : undefined}
                    title={activeTeam.is_admin ? 'Click to edit workspace name' : undefined}
                  >
                    <h3 style={{ margin: 0 }}>{activeTeam.name}</h3>
                    {activeTeam.is_admin && (
                      <button
                        type="button"
                        className={styles.editPencilBtn}
                        aria-label="Edit workspace name"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                        </svg>
                      </button>
                    )}
                  </div>
                )}

                {/* Team Description */}
                {isEditingDesc ? (
                  <div className={styles.inlineEditRow} style={{ marginTop: '8px' }}>
                    <textarea
                      className={styles.inlineEditTextarea}
                      value={descEditVal}
                      onChange={(e) => setDescEditVal(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSaveTeamDesc();
                        } else if (e.key === 'Escape') {
                          cancelEditDesc();
                        }
                      }}
                      placeholder="Describe the workspace focus or department"
                      autoFocus
                      disabled={savingEdit}
                    />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <button
                        type="button"
                        className={styles.inlineSaveBtn}
                        onClick={handleSaveTeamDesc}
                        disabled={savingEdit}
                        title="Save description (Enter)"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        className={styles.inlineCancelBtn}
                        onClick={cancelEditDesc}
                        disabled={savingEdit}
                        title="Cancel (Esc)"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div
                    className={activeTeam.is_admin ? styles.editableWrapper : undefined}
                    onClick={activeTeam.is_admin ? startEditDesc : undefined}
                    title={activeTeam.is_admin ? 'Click to edit workspace description' : undefined}
                    style={{ marginTop: '6px' }}
                  >
                    <p style={{ margin: 0 }}>
                      {activeTeam.description || (activeTeam.is_admin ? 'Click to add a workspace description...' : 'Collaborative strategy workspace for your organization.')}
                    </p>
                    {activeTeam.is_admin && (
                      <button
                        type="button"
                        className={styles.editPencilBtn}
                        aria-label="Edit workspace description"
                      >
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                        </svg>
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

            {/* ── SECTION 1: Team Projects & Access ────────────────────── */}
            {(activeFilter === 'all' || activeFilter === 'projects') && (
            <div>
              <div className={styles.sectionHeader}>
                <div className={styles.sectionTitle}>
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                  Team Projects
                  <span className={styles.sectionCounter}>{teamProjects.length}</span>
                </div>

                {activeTeam.is_admin && (
                  <button
                    type="button"
                    className={styles.btnGold}
                    onClick={() => {
                      loadAvailableProjects(activeTeam.id);
                      setGiveProjectModalOpen(true);
                    }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                    Give Project Access
                  </button>
                )}
              </div>

              {loadingProjects ? (
                <div style={{ padding: '24px', textAlign: 'center', color: '#7A746E', fontSize: '13px' }}>
                  Loading team projects...
                </div>
              ) : teamProjects.length > 0 ? (
                <div className={styles.projectsGrid}>
                  {teamProjects.map((proj) => (
                    <div key={proj.id} className={styles.projectCard}>
                      <div className={styles.projectCardTop}>
                        <div className={styles.projectIconBox}>
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                            <line x1="16" y1="13" x2="8" y2="13" />
                            <line x1="16" y1="17" x2="8" y2="17" />
                            <polyline points="10 9 9 9 8 9" />
                          </svg>
                        </div>
                        <div className={styles.projectMeta}>
                          <h4 className={styles.projectTitle} title={proj.title}>
                            {proj.title}
                          </h4>
                          <p className={styles.projectAgent}>
                            {proj.agent_type.replace(/_/g, ' ').toUpperCase()}
                          </p>
                          {proj.brand_name && (
                            <div className={styles.projectBrand}>{proj.brand_name}</div>
                          )}
                        </div>
                      </div>

                      <div className={styles.projectCardBottom}>
                        <span className={styles.projectDate}>{formatShortDate(proj.created_at)}</span>
                        {activeTeam.is_admin ? (
                          <button
                            type="button"
                            className={styles.btnDangerText}
                            onClick={() => confirmRevokeProject(proj.id, proj.title)}
                            title="Revoke project access from this team workspace"
                          >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <circle cx="12" cy="12" r="10" />
                              <line x1="15" y1="9" x2="9" y2="15" />
                              <line x1="9" y1="9" x2="15" y2="15" />
                            </svg>
                            Revoke Access
                          </button>
                        ) : (
                          <span className={styles.accessBadge}>Shared</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className={styles.emptyBox}>
                  <div style={{ color: '#A39E97', display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
                    <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                    </svg>
                  </div>
                  <h4 className={styles.emptyBoxTitle}>No projects shared yet</h4>
                  <p className={styles.emptyBoxDesc}>
                    {activeTeam.is_admin
                      ? 'Give access to your strategy projects so colleagues in this workspace can view and collaborate.'
                      : 'No strategy projects have been shared with this team workspace yet. Your team administrator will assign projects here.'}
                  </p>
                  {activeTeam.is_admin && (
                    <button
                      type="button"
                      className={styles.btnGold}
                      onClick={() => {
                        loadAvailableProjects(activeTeam.id);
                        setGiveProjectModalOpen(true);
                      }}
                      style={{ marginTop: '4px' }}
                    >
                      Give Project Access
                    </button>
                  )}
                </div>
              )}
            </div>
            )}

            {/* ── SECTION 2: Team Members & Access Permissions ────────── */}
            {(activeFilter === 'all' || activeFilter === 'members' || activeFilter === 'admins') && (
            <div>
              <div className={styles.sectionHeader}>
                <div className={styles.sectionTitle}>
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                  </svg>
                  {activeFilter === 'admins' ? 'Team Administrators' : 'Team Members'}
                  <span className={styles.sectionCounter}>
                    {activeFilter === 'admins'
                      ? (activeTeam.members || []).filter((m) => m.role === 'admin' || m.user_id === activeTeam.admin_id).length
                      : (activeTeam.members?.length || activeTeam.members_count || 1)}
                  </span>
                </div>
              </div>

              {/* Invite Teammates Section (Admin Only) */}
              {activeTeam.is_admin ? (
                <div className={styles.inviteBox}>
                  <div style={{ fontSize: '13.5px', fontWeight: 600, color: '#1A1A1A' }}>
                    Invite Teammates & Configure Initial Access
                  </div>
                  <form onSubmit={handleInviteMember} className={styles.inviteForm}>
                    <div className={styles.inviteInputsRow}>
                      <input
                        type="email"
                        placeholder="teammate@company.com"
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                        className={styles.inputEmail}
                        required
                      />
                      <RoleSelectDropdown
                        value={inviteRole}
                        onChange={(val) => setInviteRole(val)}
                      />
                      <button
                        type="submit"
                        disabled={inviting || !inviteEmail.trim()}
                        className={styles.btnPrimary}
                      >
                        {inviting ? 'Sending...' : 'Send Invitation'}
                      </button>
                    </div>

                    {/* Optional Project Restriction upon Invite */}
                    {(teamProjects.length > 0 || availableProjects.length > 0) && (
                      <div className={styles.inviteProjectsPicker}>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: '#6B6560' }}>
                          Project Access Scope:
                        </div>
                        <div className={styles.inviteRadioGroup}>
                          <label className={styles.inviteRadioLabel}>
                            <input
                              type="radio"
                              name="inviteScope"
                              checked={inviteProjectScope === 'all'}
                              onChange={() => setInviteProjectScope('all')}
                            />
                            Access all team projects
                          </label>
                          <label className={styles.inviteRadioLabel}>
                            <input
                              type="radio"
                              name="inviteScope"
                              checked={inviteProjectScope === 'custom'}
                              onChange={() => setInviteProjectScope('custom')}
                            />
                            Access only selected projects
                          </label>
                        </div>

                        {inviteProjectScope === 'custom' && (
                          <div>
                            <div className={styles.projectCheckboxesList} style={{ maxHeight: '180px' }}>
                              {teamProjects.length > 0 && availableProjects.length > 0 && (
                                <div className={styles.projectGroupHeader}>Team Projects</div>
                              )}
                              {teamProjects.map((p) => {
                                const checked = inviteSelectedProjects.includes(p.id);
                                return (
                                  <label key={p.id} className={styles.projectCheckboxItem}>
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() => {
                                        if (checked) {
                                          setInviteSelectedProjects((prev) =>
                                            prev.filter((id) => id !== p.id)
                                          );
                                        } else {
                                          setInviteSelectedProjects((prev) => [...prev, p.id]);
                                        }
                                      }}
                                    />
                                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                      {p.title}
                                    </span>
                                    <span className={styles.inTeamBadge}>Team</span>
                                  </label>
                                );
                              })}

                              {availableProjects.length > 0 && (
                                <>
                                  {teamProjects.length > 0 && (
                                    <div className={styles.projectGroupHeader}>Your Admin Projects (Will push to team)</div>
                                  )}
                                  {availableProjects.map((p) => {
                                    const checked = inviteSelectedProjects.includes(p.id);
                                    return (
                                      <label key={p.id} className={styles.projectCheckboxItem} title="Checking this project will push it to the team workspace">
                                        <input
                                          type="checkbox"
                                          checked={checked}
                                          onChange={() => {
                                            if (checked) {
                                              setInviteSelectedProjects((prev) =>
                                                prev.filter((id) => id !== p.id)
                                              );
                                            } else {
                                              setInviteSelectedProjects((prev) => [...prev, p.id]);
                                            }
                                          }}
                                        />
                                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                          {p.title}
                                        </span>
                                        <span className={styles.pushToTeamBadge}>+ Push to team</span>
                                      </label>
                                    );
                                  })}
                                </>
                              )}
                            </div>
                            {availableProjects.length > 0 && (
                              <div style={{ fontSize: '11px', color: '#8C857B', marginTop: '6px' }}>
                                Selected projects with <em>&ldquo;+ Push to team&rdquo;</em> will automatically be added to this team workspace.
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </form>

                  {feedback && (
                    <div
                      className={`${styles.feedbackBanner} ${
                        feedback.type === 'success' ? styles.feedbackSuccess : styles.feedbackError
                      }`}
                    >
                      {feedback.type === 'success' ? '✓' : '⚠'} {feedback.message}
                    </div>
                  )}
                </div>
              ) : (
                <div className={styles.nonAdminLockCard}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  <span>
                    You need <strong>admin privileges</strong> to invite teammates or configure member access. Contact your workspace administrator for invitations.
                  </span>
                </div>
              )}

              {/* Members List */}
              <div className={styles.membersContainer} style={{ marginTop: '16px' }}>
                {(() => {
                  const displayedMembers = (activeTeam.members || []).filter((member) => {
                    if (activeFilter === 'admins') {
                      return member.role === 'admin' || member.user_id === activeTeam.admin_id;
                    }
                    return true;
                  });

                  if (displayedMembers.length === 0) {
                    return (
                      <div style={{ padding: '24px', textAlign: 'center', color: '#7A746E', fontSize: '13px' }}>
                        {activeFilter === 'admins'
                          ? 'No team administrators found in this workspace.'
                          : 'No members found in this workspace.'}
                      </div>
                    );
                  }

                  return displayedMembers.map((member) => {
                    const isOwner = member.user_id === activeTeam.admin_id;
                    const isSelf = currentUserEmail === member.email;
                    const displayName = member.full_name || member.email.split('@')[0];
                    const initials = getInitials(member.full_name, member.email);
                    const hasProjectRestriction =
                      Array.isArray(member.allowed_projects) && member.allowed_projects.length > 0;

                    return (
                      <div key={member.id} className={styles.memberItem}>
                        <div className={styles.memberLeft}>
                          <div
                            className={styles.avatar}
                            style={{ backgroundColor: getAvatarColor(member.email) }}
                          >
                            {member.avatar_url ? (
                              <img src={member.avatar_url} alt="" className={styles.avatarImg} />
                            ) : (
                              initials
                            )}
                          </div>
                          <div className={styles.memberInfo}>
                            <div className={styles.memberName}>
                              {displayName}
                              {isSelf && (
                                <span style={{ fontSize: '11px', color: '#B88E28', fontWeight: 600 }}>
                                  (You)
                                </span>
                              )}
                            </div>
                            <div className={styles.memberEmail}>{member.email}</div>
                          </div>
                        </div>

                        <div className={styles.memberRight}>
                          <span
                            className={`${styles.roleBadge} ${
                              isOwner
                                ? styles.badgeOwner
                                : member.role === 'admin'
                                ? styles.badgeAdmin
                                : styles.badgeMember
                            }`}
                          >
                            {isOwner ? 'Owner' : member.role === 'admin' ? 'Admin' : 'Member'}
                          </span>

                          {/* Project Access Status Pill */}
                          <span
                            className={`${styles.accessBadge} ${
                              hasProjectRestriction ? styles.accessBadgeActive : ''
                            }`}
                          >
                            {isOwner || member.role === 'admin'
                              ? 'Full Access'
                              : hasProjectRestriction
                              ? `${member.allowed_projects?.length} Projects Allowed`
                              : 'All Team Projects'}
                          </span>

                          {/* Admin Controls: Manage Project Access & Remove Member */}
                          {activeTeam.is_admin && !isOwner && !isSelf && (
                            <>
                              <button
                                type="button"
                                className={styles.accessBtn}
                                onClick={() => openMemberPermissions(member)}
                                title="Manage project access permissions for this member"
                              >
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <path d="M12 20h9" />
                                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                                </svg>
                                Project Access
                              </button>

                              <button
                                type="button"
                                className={styles.removeBtn}
                                onClick={() => handleRemoveMember(member.user_id, member.email)}
                                disabled={removingId === member.user_id}
                                title="Remove from team"
                              >
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <line x1="18" y1="6" x2="6" y2="18" />
                                  <line x1="6" y1="6" x2="18" y2="18" />
                                </svg>
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    );
                  });
                })()}
              </div>
            </div>
            )}
          </div>
        ) : null}
      </div>

      {/* ── Give Project Access Modal ────────────────────────────────────── */}
      {giveProjectModalOpen && (
        <div className={styles.modalOverlay} onClick={() => setGiveProjectModalOpen(false)}>
          <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>Give Project Access to Team</h3>
              <button
                type="button"
                className={styles.modalCloseBtn}
                onClick={() => setGiveProjectModalOpen(false)}
              >
                ✕
              </button>
            </div>

            <div className={styles.modalBody}>
              <p style={{ fontSize: '13px', color: '#6B6560', margin: 0, lineHeight: 1.5 }}>
                Select an existing personal strategy project to share with <strong>{activeTeam?.name}</strong>. Team members will be able to access the project according to their permissions.
              </p>

              {availableProjects.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '12.5px', fontWeight: 600, color: '#1A1A1A' }}>
                    Select Project:
                  </label>
                  <select
                    className={styles.inputField}
                    value={selectedProjectIdToShare}
                    onChange={(e) => setSelectedProjectIdToShare(e.target.value)}
                  >
                    {availableProjects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title} ({p.agent_type.replace(/_/g, ' ')})
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div style={{ padding: '20px', background: '#FAF8F5', borderRadius: '10px', textAlign: 'center', fontSize: '13px', color: '#6B6560' }}>
                  All your strategy projects are already shared with this team workspace.
                </div>
              )}
            </div>

            <div className={styles.modalFooter}>
              <button
                type="button"
                className={styles.btnSecondary}
                onClick={() => setGiveProjectModalOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className={styles.btnGold}
                disabled={sharingProject || availableProjects.length === 0}
                onClick={handleGiveProjectAccess}
              >
                {sharingProject ? 'Assigning...' : 'Grant Access'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Member Project Permissions Modal ─────────────────────────────── */}
      {memberPermissionsModal.isOpen && memberPermissionsModal.member && (
        <div
          className={styles.modalOverlay}
          onClick={() => setMemberPermissionsModal((prev) => ({ ...prev, isOpen: false }))}
        >
          <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>Manage Member Project Access</h3>
              <button
                type="button"
                className={styles.modalCloseBtn}
                onClick={() => setMemberPermissionsModal((prev) => ({ ...prev, isOpen: false }))}
              >
                ✕
              </button>
            </div>

            <div className={styles.modalBody}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px', background: '#FAF8F5', borderRadius: '10px' }}>
                <div
                  className={styles.avatar}
                  style={{ backgroundColor: getAvatarColor(memberPermissionsModal.member.email), width: 32, height: 32, fontSize: 12 }}
                >
                  {getInitials(memberPermissionsModal.member.full_name, memberPermissionsModal.member.email)}
                </div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#1A1A1A' }}>
                    {memberPermissionsModal.member.full_name || memberPermissionsModal.member.email}
                  </div>
                  <div style={{ fontSize: '12px', color: '#7A746E' }}>
                    {memberPermissionsModal.member.email}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <label style={{ fontSize: '13px', fontWeight: 600, color: '#1A1A1A' }}>
                  Choose Project Access Level:
                </label>

                <div className={styles.inviteRadioGroup} style={{ flexDirection: 'column', gap: '10px' }}>
                  <label className={styles.inviteRadioLabel}>
                    <input
                      type="radio"
                      name="accessLevel"
                      checked={memberPermissionsModal.accessType === 'all'}
                      onChange={() =>
                        setMemberPermissionsModal((prev) => ({ ...prev, accessType: 'all' }))
                      }
                    />
                    <div>
                      <strong>Access all team projects</strong>
                      <div style={{ fontSize: '11.5px', color: '#7A746E' }}>
                        Member can view and participate in all current and future projects in this workspace.
                      </div>
                    </div>
                  </label>

                  <label className={styles.inviteRadioLabel}>
                    <input
                      type="radio"
                      name="accessLevel"
                      checked={memberPermissionsModal.accessType === 'custom'}
                      onChange={() =>
                        setMemberPermissionsModal((prev) => ({ ...prev, accessType: 'custom' }))
                      }
                    />
                    <div>
                      <strong>Restrict to selected projects</strong>
                      <div style={{ fontSize: '11.5px', color: '#7A746E' }}>
                        Member will only have access to the specific projects checked below.
                      </div>
                    </div>
                  </label>
                </div>

                {memberPermissionsModal.accessType === 'custom' && (
                  <div style={{ marginTop: '8px' }}>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: '#6B6560', marginBottom: '8px' }}>
                      Select Allowed Projects:
                    </div>
                    {teamProjects.length > 0 || availableProjects.length > 0 ? (
                      <div>
                        <div className={styles.projectCheckboxesList} style={{ maxHeight: '200px' }}>
                          {teamProjects.length > 0 && availableProjects.length > 0 && (
                            <div className={styles.projectGroupHeader}>Team Projects</div>
                          )}
                          {teamProjects.map((p) => {
                            const checked = memberPermissionsModal.selectedProjectIds.includes(p.id);
                            return (
                              <label key={p.id} className={styles.projectCheckboxItem}>
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => {
                                    setMemberPermissionsModal((prev) => {
                                      const next = checked
                                        ? prev.selectedProjectIds.filter((id) => id !== p.id)
                                        : [...prev.selectedProjectIds, p.id];
                                      return { ...prev, selectedProjectIds: next };
                                    });
                                  }}
                                />
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                  {p.title}
                                </span>
                                <span className={styles.inTeamBadge}>Team</span>
                              </label>
                            );
                          })}

                          {availableProjects.length > 0 && (
                            <>
                              {teamProjects.length > 0 && (
                                <div className={styles.projectGroupHeader}>Your Admin Projects (Will push to team)</div>
                              )}
                              {availableProjects.map((p) => {
                                const checked = memberPermissionsModal.selectedProjectIds.includes(p.id);
                                return (
                                  <label key={p.id} className={styles.projectCheckboxItem} title="Checking this project will push it to the team workspace">
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={() => {
                                        setMemberPermissionsModal((prev) => {
                                          const next = checked
                                            ? prev.selectedProjectIds.filter((id) => id !== p.id)
                                            : [...prev.selectedProjectIds, p.id];
                                          return { ...prev, selectedProjectIds: next };
                                        });
                                      }}
                                    />
                                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                      {p.title}
                                    </span>
                                    <span className={styles.pushToTeamBadge}>+ Push to team</span>
                                  </label>
                                );
                              })}
                            </>
                          )}
                        </div>
                        {availableProjects.length > 0 && (
                          <div style={{ fontSize: '11px', color: '#8C857B', marginTop: '6px' }}>
                            Projects with <em>&ldquo;+ Push to team&rdquo;</em> are currently under your admin account and will be automatically added to this workspace upon saving.
                          </div>
                        )}
                      </div>
                    ) : (
                      <div style={{ fontSize: '12px', color: '#7A746E', fontStyle: 'italic' }}>
                        No projects exist in this team or under your account yet.
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className={styles.modalFooter}>
              <button
                type="button"
                className={styles.btnSecondary}
                onClick={() => setMemberPermissionsModal((prev) => ({ ...prev, isOpen: false }))}
              >
                Cancel
              </button>
              <button
                type="button"
                className={styles.btnPrimary}
                disabled={savingMemberPermissions}
                onClick={saveMemberPermissions}
              >
                {savingMemberPermissions ? 'Saving...' : 'Save Permissions'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirm Modals ──────────────────────────────────────────────── */}
      <ConfirmModal
        isOpen={deleteTeamConfirm.isOpen}
        title="Delete Team Workspace"
        message={`Are you sure you want to delete the workspace "${deleteTeamConfirm.teamName}"? All team memberships will be removed.`}
        confirmLabel={deletingTeam ? 'Deleting...' : 'Delete Workspace'}
        confirmDanger
        onConfirm={doDeleteTeam}
        onCancel={() => setDeleteTeamConfirm({ isOpen: false, teamId: '', teamName: '' })}
      />

      <ConfirmModal
        isOpen={revokeProjectConfirm.isOpen}
        title="Revoke Project Access"
        message={`Are you sure you want to revoke team access for "${revokeProjectConfirm.projectTitle}"? It will be removed from this team workspace and return to personal projects.`}
        confirmLabel={revokingProject ? 'Revoking...' : 'Revoke Access'}
        confirmDanger
        onConfirm={doRevokeProject}
        onCancel={() => setRevokeProjectConfirm({ isOpen: false, projectId: '', projectTitle: '' })}
      />

      <ConfirmModal
        isOpen={removeConfirm.isOpen}
        title="Remove Member"
        message={`Are you sure you want to remove ${removeConfirm.memberEmail} from this team workspace? They will lose access to team projects immediately.`}
        confirmLabel="Remove Member"
        confirmDanger
        onConfirm={() => doRemoveMember(removeConfirm.memberId, removeConfirm.memberEmail)}
        onCancel={() => setRemoveConfirm({ isOpen: false, memberId: '', memberEmail: '' })}
      />

      <AlertModal
        isOpen={alertModal.isOpen}
        title={alertModal.title || 'Notice'}
        message={alertModal.message}
        variant="error"
        onClose={() => setAlertModal((a) => ({ ...a, isOpen: false }))}
      />

      {/* ── Toast Banner ─────────────────────────────────────────────────── */}
      {localToast && (
        <div className={styles.toastContainer}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          {localToast}
        </div>
      )}
    </div>
  );
}
