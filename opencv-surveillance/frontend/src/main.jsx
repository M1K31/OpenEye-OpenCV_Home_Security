// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

// CRITICAL: Import themes.css FIRST to establish CSS variable system
// This replaces the old global-theme.css
import './themes.css'

// Then import any page-specific overrides
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)