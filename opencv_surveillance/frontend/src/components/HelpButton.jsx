/*
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security
*/

import React, { useState, useEffect, useRef } from 'react';
import './HelpButton.css';

const HelpButton = ({ description, title }) => {
  const [showDescription, setShowDescription] = useState(false);
  const containerRef = useRef(null);
  const timeoutRef = useRef(null);

  // Close tooltip when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setShowDescription(false);
      }
    };

    if (showDescription) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [showDescription]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const handleMouseEnter = () => {
    // Clear any pending hide timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setShowDescription(true);
  };

  const handleMouseLeave = () => {
    // Delay hiding to allow moving mouse to tooltip
    timeoutRef.current = setTimeout(() => {
      setShowDescription(false);
    }, 300);
  };

  const handleClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Toggle on click for mobile/accessibility
    setShowDescription(prev => !prev);
  };

  return (
    <div 
      className="help-container" 
      ref={containerRef}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        className="question-mark-button"
        onClick={handleClick}
        aria-label="Help"
        aria-expanded={showDescription}
        type="button"
      >
        ?
      </button>
      {showDescription && (
        <div 
          className="help-description"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          {title && <strong className="help-title">{title}</strong>}
          <div className="help-content">{description}</div>
        </div>
      )}
    </div>
  );
};

export default HelpButton;
