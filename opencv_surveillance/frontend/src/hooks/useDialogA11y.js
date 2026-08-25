// Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
// This file is part of OpenEye-OpenCV_Home_Security
import { useCallback, useEffect, useRef } from 'react';

/**
 * Make a hand-rolled dialog behave like a dialog: trapped, announced, restored.
 *
 * Why this exists
 * ---------------
 * Nine components render their own overlay instead of using the shared `Modal`.
 * `useEscapeToClose` already gave them all a way out with the keyboard. Seven
 * are still missing the rest of what makes a dialog a dialog:
 *
 * - **A focus trap.** Tab from the last control and focus leaves for the page
 *   behind, which is still there and still interactive. A keyboard or screen
 *   reader user ends up operating a page they cannot see, with a dialog open on
 *   top of it.
 * - **`role="dialog"` and `aria-modal`.** Without them a screen reader announces
 *   a plain group of controls and goes on offering the whole page, so there is
 *   nothing to say that everything behind is unavailable.
 * - **Focus restoration.** Closing drops focus back to `<body>`, and the next
 *   Tab starts from the top of the page rather than from the control that
 *   opened the dialog.
 *
 * Why a hook rather than converting them
 * --------------------------------------
 * The shared `Modal` imposes its own structure — `.modal-overlay`, `.modal`,
 * `.modal-header` — and each of these dialogs has its own stylesheet built
 * around its own markup. Converting seven at once means rewriting seven layouts
 * and reconciling seven stylesheets, with visual regressions that only show up
 * by eye.
 *
 * The accessibility gap is the part that matters and the part nobody can see,
 * so it is fixed on its own. `Modal` uses this hook too, so there is one
 * implementation rather than two that drift.
 *
 * Usage
 * -----
 *     const { dialogRef, dialogProps } = useDialogA11y(isOpen, onClose, 'my-title');
 *     <div className="modal-overlay">
 *       <div ref={dialogRef} {...dialogProps} className="my-modal">
 *
 * @param {boolean}  isOpen        whether the dialog is on screen
 * @param {string}   labelledBy    id of the element naming the dialog, if any
 * @returns {{dialogRef: object, dialogProps: object}}
 */
export function useDialogA11y(isOpen = true, labelledBy = undefined) {
  const dialogRef = useRef(null);
  const previouslyFocused = useRef(null);

  const handleTab = useCallback((event) => {
    if (event.key !== 'Tab' || !dialogRef.current) return;

    const focusable = dialogRef.current.querySelectorAll(
      'a[href], button:not([disabled]), textarea:not([disabled]), ' +
      'input:not([disabled]):not([type="hidden"]), select:not([disabled]), ' +
      '[tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length === 0) {
      // Nothing to focus inside, so keep focus on the dialog itself rather
      // than letting Tab wander into the page underneath.
      event.preventDefault();
      dialogRef.current.focus();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (event.shiftKey && (active === first || active === dialogRef.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return undefined;

    // Remember where focus came from, so it can go back there on close.
    previouslyFocused.current = document.activeElement;

    // Move focus into the dialog. The first control if there is one, otherwise
    // the dialog itself — a screen reader needs focus inside to announce it.
    const node = dialogRef.current;
    if (node) {
      const firstControl = node.querySelector(
        'a[href], button:not([disabled]), textarea:not([disabled]), ' +
        'input:not([disabled]):not([type="hidden"]), select:not([disabled]), ' +
        '[tabindex]:not([tabindex="-1"])'
      );
      (firstControl || node).focus();
    }

    document.addEventListener('keydown', handleTab, true);

    return () => {
      document.removeEventListener('keydown', handleTab, true);

      // Put focus back where it was, if that element is still on the page.
      const returnTo = previouslyFocused.current;
      if (returnTo && typeof returnTo.focus === 'function' &&
          document.contains(returnTo)) {
        returnTo.focus();
      }
    };
  }, [isOpen, handleTab]);

  return {
    dialogRef,
    dialogProps: {
      role: 'dialog',
      'aria-modal': 'true',
      // Focusable programmatically but not a tab stop of its own: focus is
      // placed here deliberately, and should not be reachable by tabbing to it.
      tabIndex: -1,
      ...(labelledBy ? { 'aria-labelledby': labelledBy } : {}),
    },
  };
}

export default useDialogA11y;
