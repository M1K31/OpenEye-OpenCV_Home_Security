// Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Turn any API failure into a sentence a person can act on.
 *
 * The problem this solves
 * -----------------------
 * FastAPI answers a validation failure with `detail` as an ARRAY of error
 * objects, not a string:
 *
 *   {"detail": [{"type": "int_parsing", "loc": ["body", "face_ids", 0],
 *                "msg": "Input should be a valid integer", "input": "face-123"}]}
 *
 * Concatenating that into a message renders it as
 * "[object Object],[object Object],[object Object]" — which is what a user was
 * shown when a reassignment failed. The message named neither the field nor the
 * reason, and one object per rejected item was the only clue that three items
 * had been sent.
 *
 * Every place that reports an API error does `error.response?.data?.detail ||
 * error.message`, so all of them produce that for any 422. This is the one
 * place to fix it.
 */
export function describeApiError(error) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const parts = detail.map(describeValidationItem).filter(Boolean);
    if (parts.length) return parts.join('; ');
  }

  // Some endpoints answer with {message: ...} instead of {detail: ...}.
  const message = error?.response?.data?.message;
  if (typeof message === 'string' && message.trim()) return message;

  if (error?.message) return error.message;
  return 'Something went wrong, and the server did not say what.';
}

/**
 * One Pydantic validation error, as a phrase.
 *
 * `loc` is a path such as ["body", "face_ids", 0]; "body" carries no meaning
 * for a reader and is dropped. The offending value is included when it is small
 * enough to show, because "face_ids.0: Input should be a valid integer" is far
 * easier to act on when it also says the value was "face-123".
 */
function describeValidationItem(item) {
  if (!item || typeof item !== 'object') {
    return typeof item === 'string' ? item : null;
  }

  const path = Array.isArray(item.loc)
    ? item.loc.filter(part => part !== 'body' && part !== 'query').join('.')
    : '';
  const reason = item.msg || item.type || 'is not valid';

  let received = '';
  if (item.input !== undefined && item.input !== null) {
    const shown = typeof item.input === 'string' ? item.input : JSON.stringify(item.input);
    if (shown && shown.length <= 40) received = ` (received ${shown})`;
  }

  return path ? `${path}: ${reason}${received}` : `${reason}${received}`;
}
