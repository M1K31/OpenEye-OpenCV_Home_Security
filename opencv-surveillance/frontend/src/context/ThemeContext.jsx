// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};

export const THEMES = {
  DEFAULT: 'default',
  SUPERMAN: 'superman',
  BATMAN: 'batman',
  WONDER_WOMAN: 'wonderwoman',
  FLASH: 'flash',
  AQUAMAN: 'aquaman',
  CYBORG: 'cyborg',
  GREEN_LANTERN: 'greenlantern',
};

export const ThemeProvider = ({ children }) => {
  const [currentTheme, setCurrentTheme] = useState(() => {
    // Load theme from localStorage
    return localStorage.getItem('openeye-theme') || THEMES.DEFAULT;
  });

  useEffect(() => {
    // Save theme to localStorage
    localStorage.setItem('openeye-theme', currentTheme);
    
    // Apply theme class to body
    document.body.className = `${currentTheme}-theme`;
  }, [currentTheme]);

  const value = {
    currentTheme,
    setTheme: setCurrentTheme,
    themes: THEMES,
  };

  return (
    <ThemeContext.Provider value={value}>
      <div className={`theme-wrapper ${currentTheme}-theme`}>
        {currentTheme === THEMES.SUPERMAN && <SupermanOverlay />}
        {currentTheme === THEMES.BATMAN && <BatmanOverlay />}
        {currentTheme === THEMES.FLASH && <FlashOverlay />}
        {currentTheme === THEMES.AQUAMAN && <AquamanOverlay />}
        {currentTheme === THEMES.CYBORG && <CyborgOverlay />}
        {currentTheme === THEMES.GREEN_LANTERN && <GreenLanternOverlay />}
        {children}
      </div>
    </ThemeContext.Provider>
  );
};

// Theme Overlays
const SupermanOverlay = () => (
  <div className="superman-logo">
    <div className="superman-s">S</div>
  </div>
);

const BatmanOverlay = () => (
  <div className="bat-signal"></div>
);

const FlashOverlay = () => (
  <div className="speed-lines"></div>
);

const AquamanOverlay = () => (
  <div className="water-effect"></div>
);

const CyborgOverlay = () => (
  <div className="tech-overlay"></div>
);

const GreenLanternOverlay = () => (
  <div className="power-glow"></div>
);

export default ThemeProvider;
