// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
/**
 * User Management Page
 * v3.11.1: Full user management with ecosystem integration
 * 
 * Features:
 * - List all users (admin only)
 * - Create new users
 * - Edit user profiles
 * - Change roles
 * - Link face profiles
 * - Manage camera permissions
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/apiClient';
import { logger } from '../utils/logger';
import './UserManagementPage.css';

const UserManagementPage = () => {
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  
  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showPreferencesModal, setShowPreferencesModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    role: 'viewer',
    display_name: '',
    face_profile_name: ''
  });
  
  // Available face profiles
  const [faceProfiles, setFaceProfiles] = useState([]);
  
  // Load current user and all users on mount
  useEffect(() => {
    loadCurrentUser();
    loadUsers();
    loadFaceProfiles();
  }, []);
  
  const loadCurrentUser = async () => {
    try {
      const response = await apiClient.get('/users/me');
      setCurrentUser(response.data);
    } catch (err) {
      logger.error('Failed to load current user:', err);
    }
  };
  
  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/users/', {
        params: { page: 1, page_size: 100, include_inactive: true }
      });
      setUsers(response.data.users || []);
      setError(null);
    } catch (err) {
      setError('Failed to load users: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };
  
  const loadFaceProfiles = async () => {
    try {
      const response = await apiClient.get('/faces/people');
      const people = response.data?.data || response.data?.people || [];
      setFaceProfiles(people.map(p => p.name));
    } catch (err) {
      logger.error('Failed to load face profiles:', err);
    }
  };
  
  const handleCreateUser = async (e) => {
    e.preventDefault();
    try {
      await apiClient.post('/users/', formData);
      setShowCreateModal(false);
      resetForm();
      loadUsers();
    } catch (err) {
      setError('Failed to create user: ' + (err.response?.data?.detail || err.message));
    }
  };
  
  const handleUpdateUser = async (e) => {
    e.preventDefault();
    try {
      await apiClient.put(`/users/${selectedUser.id}`, {
        username: formData.username,
        email: formData.email,
        display_name: formData.display_name,
        face_profile_name: formData.face_profile_name
      });
      setShowEditModal(false);
      resetForm();
      loadUsers();
    } catch (err) {
      setError('Failed to update user: ' + (err.response?.data?.detail || err.message));
    }
  };
  
  const handleChangeRole = async (userId, newRole) => {
    try {
      await apiClient.patch(`/users/${userId}/role`, { role: newRole });
      loadUsers();
    } catch (err) {
      setError('Failed to change role: ' + (err.response?.data?.detail || err.message));
    }
  };
  
  const handleDeleteUser = async (userId, username) => {
    if (!window.confirm(`Are you sure you want to delete user "${username}"? This cannot be undone.`)) {
      return;
    }
    
    try {
      await apiClient.delete(`/users/${userId}`);
      loadUsers();
    } catch (err) {
      setError('Failed to delete user: ' + (err.response?.data?.detail || err.message));
    }
  };
  
  const handleLinkFace = async (userId, profileName) => {
    try {
      if (profileName) {
        await apiClient.post(`/users/${userId}/link-face`, { face_profile_name: profileName });
      } else {
        await apiClient.delete(`/users/${userId}/link-face`);
      }
      loadUsers();
    } catch (err) {
      setError('Failed to link face: ' + (err.response?.data?.detail || err.message));
    }
  };
  
  const openEditModal = (user) => {
    setSelectedUser(user);
    setFormData({
      username: user.username,
      email: user.email || '',
      password: '',
      role: user.role,
      display_name: user.display_name || '',
      face_profile_name: user.face_profile_name || ''
    });
    setShowEditModal(true);
  };
  
  const resetForm = () => {
    setFormData({
      username: '',
      email: '',
      password: '',
      role: 'viewer',
      display_name: '',
      face_profile_name: ''
    });
    setSelectedUser(null);
  };
  
  const getRoleBadgeClass = (role) => {
    switch (role) {
      case 'admin': return 'role-badge admin';
      case 'user': return 'role-badge user';
      default: return 'role-badge viewer';
    }
  };
  
  const isAdmin = currentUser?.role === 'admin';
  
  if (loading) {
    return (
      <div className="user-management-page">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading users...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="user-management-page">
      <header className="page-header">
        <div className="header-content">
          <h1>User Management</h1>
          <p className="subtitle">Manage users, roles, and permissions</p>
        </div>
        {isAdmin && (
          <button 
            className="btn btn-primary"
            onClick={() => setShowCreateModal(true)}
          >
            + Add User
          </button>
        )}
      </header>
      
      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}
      
      <div className="users-grid">
        {users.map(user => (
          <div key={user.id} className={`user-card ${!user.is_active ? 'inactive' : ''}`}>
            <div className="user-avatar">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.username} />
              ) : (
                <span className="avatar-placeholder">
                  {(user.display_name || user.username).charAt(0).toUpperCase()}
                </span>
              )}
              {user.face_profile_name && (
                <span className="face-linked-badge" title="Face profile linked">👤</span>
              )}
            </div>
            
            <div className="user-info">
              <h3>{user.display_name || user.username}</h3>
              <p className="username">@{user.username}</p>
              {user.email && <p className="email">{user.email}</p>}
              
              <div className="user-meta">
                <span className={getRoleBadgeClass(user.role)}>{user.role}</span>
                {user.two_factor_enabled && (
                  <span className="badge-2fa" title="2FA Enabled">🔐</span>
                )}
                {user.synced_from && (
                  <span className="badge-synced" title={`Synced from ${user.synced_from}`}>↔️</span>
                )}
                {!user.is_active && (
                  <span className="badge-inactive">Inactive</span>
                )}
              </div>
              
              {user.face_profile_name && (
                <p className="face-link">
                  Face: <strong>{user.face_profile_name}</strong>
                </p>
              )}
              
              {user.last_login && (
                <p className="last-login">
                  Last login: {new Date(user.last_login).toLocaleString()}
                </p>
              )}
            </div>
            
            {isAdmin && user.id !== currentUser?.id && (
              <div className="user-actions">
                <button 
                  className="btn btn-sm btn-secondary"
                  onClick={() => openEditModal(user)}
                >
                  Edit
                </button>
                <select 
                  value={user.role}
                  onChange={(e) => handleChangeRole(user.id, e.target.value)}
                  className="role-select"
                >
                  <option value="admin">Admin</option>
                  <option value="user">User</option>
                  <option value="viewer">Viewer</option>
                </select>
                <button 
                  className="btn btn-sm btn-danger"
                  onClick={() => handleDeleteUser(user.id, user.username)}
                >
                  Delete
                </button>
              </div>
            )}
            
            {user.id === currentUser?.id && (
              <div className="user-actions">
                <button 
                  className="btn btn-sm btn-secondary"
                  onClick={() => navigate('/profile')}
                >
                  My Profile
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      
      {/* Create User Modal */}
      {showCreateModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>Create New User</h2>
            <form onSubmit={handleCreateUser}>
              <div className="form-group">
                <label>Username *</label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({...formData, username: e.target.value})}
                  required
                  minLength={3}
                />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                />
              </div>
              <div className="form-group">
                <label>Password *</label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({...formData, password: e.target.value})}
                  required
                  minLength={8}
                />
              </div>
              <div className="form-group">
                <label>Display Name</label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({...formData, display_name: e.target.value})}
                  placeholder="Friendly display name"
                />
              </div>
              <div className="form-group">
                <label>Role</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({...formData, role: e.target.value})}
                >
                  <option value="viewer">Viewer (Read-only)</option>
                  <option value="user">User (Can control cameras)</option>
                  <option value="admin">Admin (Full access)</option>
                </select>
              </div>
              <div className="form-group">
                <label>Link Face Profile</label>
                <select
                  value={formData.face_profile_name}
                  onChange={(e) => setFormData({...formData, face_profile_name: e.target.value})}
                >
                  <option value="">-- No face profile --</option>
                  {faceProfiles.map(name => (
                    <option key={name} value={name}>{name}</option>
                  ))}
                </select>
                <small>Link to a face recognition profile for automatic detection</small>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => {
                  setShowCreateModal(false);
                  resetForm();
                }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Create User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      {/* Edit User Modal */}
      {showEditModal && selectedUser && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>Edit User: {selectedUser.username}</h2>
            <form onSubmit={handleUpdateUser}>
              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={(e) => setFormData({...formData, username: e.target.value})}
                  required
                />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({...formData, email: e.target.value})}
                />
              </div>
              <div className="form-group">
                <label>Display Name</label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({...formData, display_name: e.target.value})}
                  placeholder="Friendly display name"
                />
              </div>
              <div className="form-group">
                <label>Link Face Profile</label>
                <select
                  value={formData.face_profile_name}
                  onChange={(e) => setFormData({...formData, face_profile_name: e.target.value})}
                >
                  <option value="">-- No face profile --</option>
                  {faceProfiles.map(name => (
                    <option key={name} value={name}>{name}</option>
                  ))}
                </select>
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => {
                  setShowEditModal(false);
                  resetForm();
                }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      {/* Info Panel */}
      <div className="info-panel">
        <h3>User Roles</h3>
        <ul>
          <li><strong>Admin:</strong> Full system access. Can manage users, cameras, and all settings.</li>
          <li><strong>User:</strong> Can view and control cameras, manage their own settings and face profiles.</li>
          <li><strong>Viewer:</strong> Read-only access. Can view camera feeds and recordings.</li>
        </ul>
        <h3>Face Profile Linking</h3>
        <p>
          Link a user account to a face recognition profile to enable:
        </p>
        <ul>
          <li>Automatic detection when the user is on camera</li>
          <li>Personalized notifications when the user arrives home</li>
          <li>Home presence detection for automations</li>
          <li>User-specific event routing to devices</li>
        </ul>
      </div>
    </div>
  );
};

export default UserManagementPage;


