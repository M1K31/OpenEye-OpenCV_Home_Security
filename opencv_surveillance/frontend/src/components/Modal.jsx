// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useEffect, useRef, useCallback } from 'react';
import './Modal.css';

/**
 * Modal Component - Accessible modal dialog with backdrop blur
 * 
 * Features:
 * - Focus trap (focus stays within modal)
 * - Escape key to close
 * - Click outside to close
 * - Smooth animations with backdrop blur effect
 * - Respects reduce-motion preferences
 * - Theme-aware styling
 * - Accessible (ARIA attributes, focus management)
 * 
 * @param {boolean} isOpen - Controls modal visibility
 * @param {function} onClose - Called when modal should close
 * @param {string} title - Modal title (aria-labelledby)
 * @param {ReactNode} children - Modal content
 * @param {string} size - 'sm', 'md', 'lg', 'xl'
 * @param {boolean} showCloseButton - Show X button in corner
 * @param {boolean} closeOnBackdropClick - Allow closing by clicking outside
 * @param {boolean} closeOnEscape - Allow closing with Escape key
 */
const Modal = ({ 
  isOpen = false,
  onClose,
  title,
  children,
  size = 'md',
  showCloseButton = true,
  closeOnBackdropClick = true,
  closeOnEscape = true,
  footer = null
}) => {
  const modalRef = useRef(null);
  const previousFocusRef = useRef(null);

  // Focus trap - cycle through focusable elements
  const trapFocus = useCallback((e) => {
    if (!modalRef.current || e.key !== 'Tab') return;

    const focusableElements = modalRef.current.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    if (e.shiftKey) {
      // Shift + Tab
      if (document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      }
    } else {
      // Tab
      if (document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    }
  }, []);

  // Handle escape key
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape' && closeOnEscape) {
      onClose();
    }
    trapFocus(e);
  }, [closeOnEscape, onClose, trapFocus]);

  // Focus management
  useEffect(() => {
    if (isOpen) {
      // Save current focus
      previousFocusRef.current = document.activeElement;
      
      // Focus modal
      setTimeout(() => {
        modalRef.current?.focus();
      }, 100); // Delay for animation
      
      // Prevent body scroll
      document.body.style.overflow = 'hidden';
      
      // Add keyboard listener
      document.addEventListener('keydown', handleKeyDown);
    } else {
      // Restore focus
      if (previousFocusRef.current && previousFocusRef.current.focus) {
        previousFocusRef.current.focus();
      }
      
      // Restore body scroll
      document.body.style.overflow = '';
      
      // Remove keyboard listener
      document.removeEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, handleKeyDown]);

  // Handle backdrop click
  const handleBackdropClick = (e) => {
    if (closeOnBackdropClick && e.target === e.currentTarget) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      onClick={handleBackdropClick}
      aria-modal="true"
      role="presentation"
    >
      <div
        ref={modalRef}
        className={`modal modal-${size}`}
        onClick={(e) => e.stopPropagation()}
        tabIndex={-1}
        role="dialog"
        aria-labelledby="modal-title"
        aria-describedby="modal-description"
      >
        {/* Header with title and close button */}
        <div className="modal-header">
          {title && (
            <h2 id="modal-title" className="modal-title">
              {title}
            </h2>
          )}
          {showCloseButton && (
            <button
              className="modal-close"
              onClick={onClose}
              aria-label="Close modal"
              type="button"
            >
              ×
            </button>
          )}
        </div>

        {/* Content */}
        <div id="modal-description" className="modal-body">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="modal-footer">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Confirmation Modal - Quick confirmation dialog
 */
export const ConfirmModal = ({ 
  isOpen, 
  onClose, 
  onConfirm, 
  title = 'Confirm Action',
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  variant = 'primary' // 'primary', 'danger'
}) => {
  const handleConfirm = () => {
    onConfirm();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      <p style={{ marginBottom: '24px' }}>{message}</p>
      <div className="modal-footer">
        <button
          className="btn btn-secondary"
          onClick={onClose}
          type="button"
        >
          {cancelText}
        </button>
        <button
          className={`btn btn-${variant}`}
          onClick={handleConfirm}
          type="button"
        >
          {confirmText}
        </button>
      </div>
    </Modal>
  );
};

export default Modal;
