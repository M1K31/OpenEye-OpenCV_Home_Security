// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye.
import React from 'react';
import { Link } from 'react-router-dom';

const DashboardPage = ({ onLogout }) => {
  const streamUrl = "/api/cameras/mock_cam_1/stream";

  return (
    <div>
      <h1>Surveillance Dashboard</h1>
      <div className="video-container">
        <img src={streamUrl} alt="Live camera stream" className="video-stream" />
      </div>
      <div style={{ marginTop: '1rem' }}>
        <Link to="/face-management" style={{ marginRight: '1rem' }}>
          <button>Manage Faces</button>
        </Link>
        <button onClick={onLogout}>Logout</button>
      </div>
    </div>
  );
};

export default DashboardPage;