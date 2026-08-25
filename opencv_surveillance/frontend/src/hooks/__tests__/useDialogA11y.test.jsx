// Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
// This file is part of OpenEye-OpenCV_Home_Security
//
// A dialog has to hold on to focus.
//
// Nine components render their own overlay rather than using the shared Modal.
// All had a way out with the keyboard; seven had nothing else — no focus trap,
// no role, no aria-modal, no focus restoration. Tab from the last control and
// focus left for the page behind, which was still there and still interactive,
// so a keyboard or screen reader user ended up operating a page they could not
// see with a dialog open on top of it.
//
// Tested through a real component rather than by inspecting the hook, because
// the property that matters is where focus actually ends up.

import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { useDialogA11y } from '../useDialogA11y';

afterEach(cleanup);

function Dialog({ labelledBy = 'title', children }) {
  const { dialogRef, dialogProps } = useDialogA11y(true, labelledBy);
  return (
    <div ref={dialogRef} {...dialogProps} data-testid="dialog">
      <h2 id="title">A dialog</h2>
      {children}
    </div>
  );
}

describe('a dialog announces itself', () => {
  it('carries the dialog role', () => {
    render(<Dialog><button>ok</button></Dialog>);
    expect(screen.getByTestId('dialog')).toHaveAttribute('role', 'dialog');
  });

  it('declares that the rest of the page is unavailable', () => {
    render(<Dialog><button>ok</button></Dialog>);
    expect(screen.getByTestId('dialog')).toHaveAttribute('aria-modal', 'true');
  });

  it('is named by its heading', () => {
    render(<Dialog><button>ok</button></Dialog>);
    expect(screen.getByTestId('dialog')).toHaveAttribute('aria-labelledby', 'title');
  });

  it('is focusable programmatically but is not a tab stop', () => {
    // Focus is placed there deliberately on open; tabbing to the container
    // itself would be a stop that does nothing.
    render(<Dialog><button>ok</button></Dialog>);
    expect(screen.getByTestId('dialog')).toHaveAttribute('tabindex', '-1');
  });

  it('omits aria-labelledby when there is nothing to point at', () => {
    // `null` rather than `undefined`: a default parameter fires on undefined,
    // so passing that would silently test the default instead.
    render(<Dialog labelledBy={null}><button>ok</button></Dialog>);
    expect(screen.getByTestId('dialog')).not.toHaveAttribute('aria-labelledby');
  });
});

describe('focus on open', () => {
  it('moves into the dialog, to its first control', () => {
    render(<Dialog><button>first</button><button>second</button></Dialog>);
    expect(document.activeElement).toBe(screen.getByText('first'));
  });

  it('falls back to the dialog itself when it holds no controls', () => {
    // A screen reader needs focus inside to announce the dialog at all.
    render(<Dialog><p>Nothing to do here</p></Dialog>);
    expect(document.activeElement).toBe(screen.getByTestId('dialog'));
  });

  it('skips a disabled control', () => {
    render(
      <Dialog>
        <button disabled>cannot</button>
        <button>can</button>
      </Dialog>
    );
    expect(document.activeElement).toBe(screen.getByText('can'));
  });
});

describe('the trap', () => {
  it('sends Tab from the last control back to the first', () => {
    render(<Dialog><button>first</button><button>last</button></Dialog>);
    const last = screen.getByText('last');
    last.focus();

    fireEvent.keyDown(document, { key: 'Tab' });

    expect(document.activeElement).toBe(screen.getByText('first'));
  });

  it('sends Shift+Tab from the first control to the last', () => {
    render(<Dialog><button>first</button><button>last</button></Dialog>);
    screen.getByText('first').focus();

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });

    expect(document.activeElement).toBe(screen.getByText('last'));
  });

  it('leaves Tab alone in the middle of the dialog', () => {
    // Only the edges are redirected; the browser handles the rest.
    render(
      <Dialog>
        <button>first</button><button>middle</button><button>last</button>
      </Dialog>
    );
    const middle = screen.getByText('middle');
    middle.focus();

    fireEvent.keyDown(document, { key: 'Tab' });

    expect(document.activeElement).toBe(middle);
  });

  it('keeps focus in a dialog that has no controls at all', () => {
    render(<Dialog><p>Nothing to do here</p></Dialog>);

    fireEvent.keyDown(document, { key: 'Tab' });

    expect(document.activeElement).toBe(screen.getByTestId('dialog'));
  });

  it('ignores keys that are not Tab', () => {
    render(<Dialog><button>first</button><button>last</button></Dialog>);
    const last = screen.getByText('last');
    last.focus();

    fireEvent.keyDown(document, { key: 'a' });

    expect(document.activeElement).toBe(last);
  });
});

describe('focus on close', () => {
  it('goes back to whatever opened the dialog', () => {
    const opener = document.createElement('button');
    opener.textContent = 'open';
    document.body.appendChild(opener);
    opener.focus();

    const { unmount } = render(<Dialog><button>inside</button></Dialog>);
    expect(document.activeElement).not.toBe(opener);

    unmount();

    expect(document.activeElement).toBe(opener);
    opener.remove();
  });

  it('does not throw when the opener has since been removed', () => {
    const opener = document.createElement('button');
    document.body.appendChild(opener);
    opener.focus();

    const { unmount } = render(<Dialog><button>inside</button></Dialog>);
    opener.remove();

    expect(() => unmount()).not.toThrow();
  });
});
