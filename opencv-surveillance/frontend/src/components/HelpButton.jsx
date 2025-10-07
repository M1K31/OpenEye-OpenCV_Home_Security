/*
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security
*/

import React, { useState } from 'react';
import './HelpButton.css';

const HelpButton = ({ description, title }) => {
  const [showDescription, setShowDescription] = useState(false);

  return (
    <div className="help-container">
      <button
        className="question-mark-button"
        onMouseEnter={() => setShowDescription(true)}
        onMouseLeave={() => setShowDescription(false)}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setShowDescription(!showDescription);
        }}
        aria-label="Help"
        type="button"
      >
        ?
      </button>
      {showDescription && (
        <div className="help-description">
          {title && <strong className="help-title">{title}</strong>}
          <div className="help-content">{description}</div>
        </div>
      )}
    </div>
  );
};

export default HelpButton;
