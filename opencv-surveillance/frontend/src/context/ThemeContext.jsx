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
  SUPERMAN: 'sman',
  BATMAN: 'bman',
  WONDER_WOMAN: 'wwoman',
  FLASH: 'fman',
  AQUAMAN: 'aman',
  CYBORG: 'cyborg',
  GREEN_LANTERN: 'glantern',
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
        {children}
      </div>
    </ThemeContext.Provider>
  );
};

export default ThemeProvider;
