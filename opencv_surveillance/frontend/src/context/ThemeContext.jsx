// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { createContext, useContext, useState, useEffect } from 'react';
import { logger } from '../utils/logger';

const ThemeContext = createContext();

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};

// Descriptive, non-infringing palette names (audit F-09). Previous identifiers
// referenced third-party characters and were an App Store IP-rejection risk.
export const THEMES = {
  DEFAULT: 'default',
  STEEL_BLUE: 'steel',
  MIDNIGHT: 'midnight',
  CRIMSON_GOLD: 'crimson',
  SCARLET: 'scarlet',
  TIDAL: 'tidal',
  CIRCUIT: 'circuit',
  EMERALD: 'emerald',
  AQUA_SECURITY: 'aquasecurity',
};

export const ThemeProvider = ({ children }) => {
  const [currentTheme, setCurrentTheme] = useState(() => {
    // Load theme from localStorage
    return localStorage.getItem('openeye-theme') || THEMES.DEFAULT;
  });

  useEffect(() => {
    // Save theme to localStorage
    localStorage.setItem('openeye-theme', currentTheme);
    
    // CRITICAL: Apply theme class to html element (documentElement) for maximum CSS specificity
    // This ensures :root variables are properly scoped to the theme
    const htmlElement = document.documentElement;
    
    // Remove all existing theme classes
    Object.values(THEMES).forEach(theme => {
      htmlElement.classList.remove(`${theme}-theme`);
    });
    
    // Add current theme class
    htmlElement.classList.add(`${currentTheme}-theme`);

    // Also apply to body for backward compatibility.
    //
    // Assigning to className would replace the ENTIRE class list, silently
    // erasing anything another component put there — a modal's scroll lock, a
    // feature flag, a page-specific class — every time the theme changed. Use
    // the same additive pattern as the html element above, so this only ever
    // touches classes it owns.
    Object.values(THEMES).forEach(theme => {
      document.body.classList.remove(`${theme}-theme`);
    });
    document.body.classList.add(`${currentTheme}-theme`);

    logger.log(`[ThemeContext] Applied theme: ${currentTheme}`);
  }, [currentTheme]);

  const value = {
    currentTheme,
    setTheme: setCurrentTheme,
    themes: THEMES,
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};

export default ThemeProvider;
