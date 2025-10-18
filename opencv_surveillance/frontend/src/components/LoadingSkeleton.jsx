// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React from 'react';
import './LoadingSkeleton.css';

/**
 * LoadingSkeleton - Shimmer loading animation component
 * 
 * Provides skeleton screens for better perceived performance during loading
 * Respects reduce-motion preferences
 * Theme-aware styling
 * 
 * @param {string} variant - 'text', 'card', 'avatar', 'button', 'video'
 * @param {number} width - Width in pixels or percentage string
 * @param {number} height - Height in pixels
 * @param {number} count - Number of skeleton elements to render
 * @param {boolean} rounded - Apply rounded corners
 */
const LoadingSkeleton = ({ 
  variant = 'text', 
  width, 
  height, 
  count = 1,
  rounded = false,
  className = ''
}) => {
  
  const getVariantStyles = () => {
    switch (variant) {
      case 'text':
        return {
          width: width || '100%',
          height: height || '16px',
          borderRadius: 'var(--radius-sm, 8px)'
        };
      case 'card':
        return {
          width: width || '100%',
          height: height || '200px',
          borderRadius: 'var(--radius-md, 12px)'
        };
      case 'avatar':
        return {
          width: width || '44px',
          height: height || '44px',
          borderRadius: '50%'
        };
      case 'button':
        return {
          width: width || '120px',
          height: height || 'var(--touch-target-min, 44px)',
          borderRadius: 'var(--radius-pill, 999px)'
        };
      case 'video':
        return {
          width: width || '100%',
          height: height || '0',
          paddingBottom: height ? '0' : '56.25%', // 16:9 aspect ratio
          borderRadius: 'var(--radius-md, 12px)'
        };
      default:
        return {
          width: width || '100%',
          height: height || '16px',
          borderRadius: 'var(--radius-sm, 8px)'
        };
    }
  };

  const skeletonStyles = {
    ...getVariantStyles(),
    ...(rounded && { borderRadius: 'var(--radius-pill, 999px)' })
  };

  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className={`skeleton ${variant} ${className}`}
          style={skeletonStyles}
          aria-label="Loading..."
          role="status"
        />
      ))}
    </>
  );
};

/**
 * Pre-configured skeleton patterns for common use cases
 */
export const SkeletonCard = () => (
  <div className="skeleton-card-container">
    <LoadingSkeleton variant="card" height={200} />
    <div style={{ padding: 'var(--spacing-md, 16px)' }}>
      <LoadingSkeleton variant="text" width="60%" height={20} />
      <LoadingSkeleton variant="text" width="100%" height={16} count={2} />
    </div>
  </div>
);

export const SkeletonCameraCard = () => (
  <div className="skeleton-camera-card">
    <LoadingSkeleton variant="video" />
    <div style={{ padding: 'var(--spacing-md, 16px)', display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm, 8px)' }}>
      <LoadingSkeleton variant="text" width="70%" height={18} />
      <LoadingSkeleton variant="text" width="50%" height={14} />
    </div>
  </div>
);

export const SkeletonList = ({ count = 5 }) => (
  <div className="skeleton-list">
    {Array.from({ length: count }).map((_, index) => (
      <div key={index} className="skeleton-list-item">
        <LoadingSkeleton variant="avatar" width={44} height={44} />
        <div style={{ flex: 1 }}>
          <LoadingSkeleton variant="text" width="40%" height={16} />
          <LoadingSkeleton variant="text" width="80%" height={14} />
        </div>
      </div>
    ))}
  </div>
);

export const SkeletonEventTimeline = ({ count = 10 }) => (
  <div className="skeleton-timeline">
    {Array.from({ length: count }).map((_, index) => (
      <div key={index} className="skeleton-timeline-item">
        <LoadingSkeleton variant="avatar" width={40} height={40} />
        <div style={{ flex: 1 }}>
          <LoadingSkeleton variant="text" width="60%" height={16} />
          <LoadingSkeleton variant="text" width="90%" height={12} />
          <LoadingSkeleton variant="text" width="40%" height={12} />
        </div>
      </div>
    ))}
  </div>
);

export default LoadingSkeleton;
