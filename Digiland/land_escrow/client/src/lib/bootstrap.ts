export interface BootstrapData {
  [key: string]: any;
}

export function readBootstrap(): BootstrapData {
  if (typeof document === 'undefined') {
    return {};
  }

  const script = document.getElementById('digiland-bootstrap');
  if (!script) {
    return {};
  }

  const raw = script.textContent?.trim();
  if (!raw) {
    return {};
  }

  try {
    return JSON.parse(raw) as BootstrapData;
  } catch (error) {
    console.error('[digiland] Failed to parse bootstrap payload', error);
    return {};
  }
}
