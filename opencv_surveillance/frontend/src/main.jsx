// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

// CRITICAL: Import themes.css FIRST to establish CSS variable system
// This replaces the old global-theme.css
import './themes.css'
// Bridge must come AFTER themes.css: it defines the token names component CSS
// actually consumes, in terms of the palette tokens themes.css just declared.
import './theme-bridge.css'

// Import global component styles (buttons, modals, forms, etc.)
import './styles/global-components.css'

// Then import any page-specific overrides
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)