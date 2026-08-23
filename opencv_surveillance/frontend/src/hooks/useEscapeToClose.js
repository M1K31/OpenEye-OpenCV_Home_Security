// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import { useEffect } from 'react';

/**
 * Close a dialog when Escape is pressed.
 *
 * Why this exists
 * ---------------
 * The shared `Modal` component is properly accessible — focus trap, Escape,
 * ARIA roles. Eleven dialogs do not use it; they render their own
 * `.modal-overlay` and close only on a mouse click on the backdrop or a button.
 * A keyboard user could open those and have no way to dismiss them.
 *
 * Refactoring all eleven onto `Modal` is the better end state, but it changes
 * their markup and layout, so this hook restores the missing behaviour without
 * touching how they look. New dialogs should use `Modal` rather than this.
 *
 * Deliberately does not add `tabIndex` to the backdrop. A backdrop is not a
 * control: making it focusable inserts a tab stop that does nothing, which is a
 * different accessibility problem rather than a fix for this one.
 *
 * @param {Function} onClose  called when Escape is pressed
 * @param {boolean}  isOpen   skip the listener while the dialog is closed
 */
export function useEscapeToClose(onClose, isOpen = true) {
  useEffect(() => {
    if (!isOpen || typeof onClose !== 'function') return undefined;

    const handleKeyDown = (event) => {
      if (event.key !== 'Escape') return;
      // Stop the event reaching a dialog underneath this one, so nested
      // dialogs close one layer at a time rather than all at once.
      event.stopPropagation();
      onClose();
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose, isOpen]);
}

export default useEscapeToClose;
