// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme, THEMES } from '../context/ThemeContext';
import HelpButton from '../components/HelpButton';
import { HELP_CONTENT } from '../utils/helpContent';

const ThemeSelectorPage = ({ embedded = false }) => {
  const navigate = useNavigate();
  const { currentTheme, setTheme } = useTheme();
  const [previewTheme, setPreviewTheme] = useState(currentTheme);

  const themeInfo = {
    [THEMES.DEFAULT]: {
      name: 'Default',
      icon: '🎨',
      description: 'Clean and professional design',
      colors: ['#667eea', '#764ba2', '#f8f9fa'],
    },
    [THEMES.SUPERMAN]: {
      name: 'Sman',
      icon: 'S',
      description: 'Classic red/blue with hope and power',
      colors: ['#0076a8', '#d32029', '#f2c700'],
    },
    [THEMES.BATMAN]: {
      name: 'Bman',
      icon: '🦇',
      description: 'Dark knight - brooding and mysterious',
      colors: ['#111', '#333', '#edc233'],
    },
    [THEMES.WONDER_WOMAN]: {
      name: 'W Woman',
      icon: '⭐',
      description: 'Warrior gold - regal and vibrant',
      colors: ['#a41b30', '#0074fa', '#f4d975'],
    },
    [THEMES.FLASH]: {
      name: 'Flah',
      icon: '⚡',
      description: 'Speed red - dynamic and energetic',
      colors: ['#b90000', '#f4be00', '#fff'],
    },
    [THEMES.AQUAMAN]: {
      name: 'Aman',
      icon: '🔱',
      description: 'Ocean teal - deep sea depths',
      colors: ['#005642', '#d9c27f', '#7c4c2d'],
    },
    [THEMES.CYBORG]: {
      name: 'Cy',
      icon: '🤖',
      description: 'Tech silver - modern neon highlights',
      colors: ['#1a1a1a', '#555', '#ff00ff'],
    },
    [THEMES.GREEN_LANTERN]: {
      name: 'G Lantern',
      icon: '💚',
      description: 'Willpower green - cosmic power glow',
      colors: ['#00a064', '#007447', '#222'],
    },
  };

  const applyTheme = (theme) => {
    setTheme(theme);
    setPreviewTheme(theme);
  };

  // Safety check: ensure currentTheme exists in themeInfo
  const safeCurrentTheme = themeInfo[currentTheme] ? currentTheme : THEMES.DEFAULT;
  const currentThemeData = themeInfo[safeCurrentTheme];

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        {!embedded && (
          <button onClick={() => navigate('/')} style={styles.backButton}>
            ← Back to Dashboard
          </button>
        )}
        <h1 style={styles.title}>
          🎨 Theme Selector
          <HelpButton 
            title={HELP_CONTENT.THEMES.title}
            description={HELP_CONTENT.THEMES.description}
          />
        </h1>
        <p style={styles.subtitle}>
          Choose your favorite superhero theme or stick with the classic design
        </p>
      </div>

      <div style={styles.currentTheme}>
        <span style={styles.label}>Current Theme:</span>
        <span style={styles.themeName}>
          {currentThemeData.icon} {currentThemeData.name}
        </span>
      </div>

      <div style={styles.themeGrid}>
        {Object.entries(THEMES).map(([key, themeId]) => {
          const info = themeInfo[themeId];
          const isActive = currentTheme === themeId;
          const isPreviewing = previewTheme === themeId;

          return (
            <div
              key={themeId}
              style={{
                ...styles.themeCard,
                ...(isActive ? styles.themeCardActive : {}),
                ...(isPreviewing ? styles.themeCardPreview : {}),
              }}
              onClick={() => setPreviewTheme(themeId)}
            >
              <div style={styles.cardHeader}>
                <div style={styles.themeIcon}>{info.icon}</div>
                <h3 style={styles.themeName}>{info.name}</h3>
                {isActive && <span style={styles.activeBadge}>✓ Active</span>}
              </div>

              <p style={styles.themeDescription}>{info.description}</p>

              <div style={styles.colorPalette}>
                {info.colors.map((color, idx) => (
                  <div
                    key={idx}
                    style={{
                      ...styles.colorSwatch,
                      backgroundColor: color,
                    }}
                    title={color}
                  />
                ))}
              </div>

              <div style={styles.cardActions}>
                {!isActive ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      applyTheme(themeId);
                    }}
                    style={styles.applyButton}
                  >
                    Apply Theme
                  </button>
                ) : (
                  <div style={styles.currentLabel}>Currently Active</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div style={styles.infoSection}>
        <h3 style={styles.infoTitle}>💡 About Themes</h3>
        <div style={styles.infoGrid}>
          <div style={styles.infoCard}>
            <h4>🎭 Personalization</h4>
            <p>Each theme transforms the entire interface with unique colors, fonts, and animations</p>
          </div>
          <div style={styles.infoCard}>
            <h4>💾 Persistent</h4>
            <p>Your theme choice is saved locally and persists across sessions</p>
          </div>
          <div style={styles.infoCard}>
            <h4>⚡ Performance</h4>
            <p>Themes use CSS for smooth animations without impacting performance</p>
          </div>
        </div>
      </div>
    </div>
  );
};

const styles = {
  container: {
    padding: '20px',
    maxWidth: '1400px',
    margin: '0 auto',
    fontFamily: 'Arial, sans-serif',
    backgroundColor: 'var(--bg-main)',
    minHeight: '100vh',
    color: 'var(--text-primary)',
  },
  header: {
    marginBottom: '30px',
  },
  backButton: {
    background: 'var(--bg-panel)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-panel)',
    color: 'white',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
    marginBottom: '15px',
  },
  title: {
    fontSize: '32px',
    marginBottom: '10px',
  },
  subtitle: {
    fontSize: '16px',
    opacity: 0.8,
  },
  currentTheme: {
    background: 'rgba(255,255,255,0.05)',
    padding: '15px 25px',
    borderRadius: '10px',
    marginBottom: '30px',
    display: 'flex',
    alignItems: 'center',
    gap: '15px',
  },
  label: {
    fontWeight: 'bold',
    fontSize: '16px',
  },
  themeName: {
    fontSize: '20px',
    fontWeight: 'bold',
  },
  themeGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '25px',
    marginBottom: '40px',
  },
  themeCard: {
    background: 'var(--bg-panel)',
    color: '#2c3e50',
    borderRadius: '15px',
    padding: '25px',
    cursor: 'pointer',
    transition: 'all 0.3s',
    border: '3px solid transparent',
  },
  themeCardActive: {
    border: '3px solid #28a745',
    boxShadow: '0 0 20px rgba(40,167,69,0.3)',
  },
  themeCardPreview: {
    transform: 'scale(1.02)',
    boxShadow: '0 8px 16px rgba(0,0,0,0.2)',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '15px',
    marginBottom: '15px',
    position: 'relative',
  },
  themeIcon: {
    fontSize: '48px',
    width: '60px',
    height: '60px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--bg-panel)',
    borderRadius: '10px',
  },
  activeBadge: {
    position: 'absolute',
    top: 0,
    right: 0,
    background: 'var(--color-success)',
    color: 'white',
    padding: '4px 12px',
    borderRadius: '15px',
    fontSize: '12px',
    fontWeight: 'bold',
  },
  themeDescription: {
    fontSize: '14px',
    marginBottom: '20px',
    lineHeight: '1.6',
    opacity: 0.9,
    color: '#88c0d0', // Light blue for better readability on dark backgrounds
  },
  colorPalette: {
    display: 'flex',
    gap: '8px',
    marginBottom: '20px',
  },
  colorSwatch: {
    width: '40px',
    height: '40px',
    borderRadius: '8px',
    border: '2px solid rgba(0,0,0,0.1)',
  },
  cardActions: {
    marginTop: '15px',
  },
  applyButton: {
    width: '100%',
    background: 'var(--text-link)',
    color: 'white',
    border: 'none',
    padding: '12px',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
    transition: 'all 0.2s',
  },
  currentLabel: {
    textAlign: 'center',
    color: '#28a745',
    fontWeight: 'bold',
    fontSize: '16px',
  },
  infoSection: {
    background: 'rgba(255,255,255,0.05)',
    borderRadius: '15px',
    padding: '30px',
  },
  infoTitle: {
    fontSize: '24px',
    marginBottom: '20px',
  },
  infoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
    gap: '20px',
  },
  infoCard: {
    background: 'var(--bg-panel)',
    color: 'var(--text-primary)',
    padding: '20px',
    borderRadius: '10px',
  },
};

export default ThemeSelectorPage;
