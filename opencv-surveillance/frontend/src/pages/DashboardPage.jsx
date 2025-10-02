import React from 'react';

const DashboardPage = ({ onLogout }) => {
  const streamUrl = "/api/cameras/mock_cam_1/stream";

  return (
    <div>
      <h1>Surveillance Dashboard</h1>
      <div className="video-container">
        <img src={streamUrl} alt="Live camera stream" className="video-stream" />
      </div>
      <button onClick={onLogout}>Logout</button>
    </div>
  );
};

export default DashboardPage;