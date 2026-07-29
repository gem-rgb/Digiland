export type ErrorSeverity = 'critical' | 'error' | 'warning' | 'info';

function randomSegment(length = 6): string {
  const alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const bytes = new Uint8Array(length);

  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }

  return Array.from(bytes, (value) => alphabet[value % alphabet.length]).join('');
}

export function generateReferenceId(prefix = 'DL'): string {
  const timestamp = Date.now().toString(36).toUpperCase();
  return `${prefix}-${timestamp}-${randomSegment(6)}`;
}
