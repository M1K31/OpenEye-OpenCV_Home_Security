// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye.
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

const DashboardPage = ({ onLogout }) => {
  const streamUrl = "/api/cameras/mock_cam_1/stream";
  const [showFaceManagement, setShowFaceManagement] = useState(false);
  const navigate = useNavigate();

  const styles = {
    headerButtons: {
      display: 'flex',
      gap: '1rem',
      marginTop: '1rem'
    },
    alertButton: {
      backgroundColor: '#ff9800',
      color: 'white',
      padding: '10px 20px',
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      fontWeight: 'bold',
    },
    faceButton: {
      backgroundColor: '#2196f3',
      color: 'white',
      padding: '10px 20px',
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      fontWeight: 'bold',
    },
    logoutButton: {
      backgroundColor: '#f44336',
      color: 'white',
      padding: '10px 20px',
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      fontWeight: 'bold',
    }
  };

  return (
    <div>
      <h1>Surveillance Dashboard</h1>
      <div className="video-container">
        <img src={streamUrl} alt="Live camera stream" className="video-stream" />
      </div>
      
      <div style={styles.headerButtons}>
        <button onClick={() => navigate('/alerts')} style={styles.alertButton}>
          🔔 Alert Settings
        </button>
        <button onClick={() => setShowFaceManagement(true)} style={styles.faceButton}>
          👤 Manage Faces
        </button>
        <button onClick={onLogout} style={styles.logoutButton}>
          Logout
        </button>
      </div>
    </div>
  );
};

export default DashboardPage;