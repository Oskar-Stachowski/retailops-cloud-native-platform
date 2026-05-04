export const DEFAULT_DEMO_USER_ID = "platform-admin";
export const DEMO_USER_STORAGE_KEY = "retailops.demoUserId";
export const DEMO_USER_CHANGED_EVENT = "retailops:demo-user-changed";

export function getSelectedDemoUserId() {
  if (typeof window === "undefined") {
    return DEFAULT_DEMO_USER_ID;
  }

  return window.localStorage.getItem(DEMO_USER_STORAGE_KEY) || DEFAULT_DEMO_USER_ID;
}

export function setSelectedDemoUserId(userId) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(DEMO_USER_STORAGE_KEY, userId || DEFAULT_DEMO_USER_ID);
}

export function emitDemoUserChanged(userId) {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(
    new CustomEvent(DEMO_USER_CHANGED_EVENT, {
      detail: { userId: userId || DEFAULT_DEMO_USER_ID },
    }),
  );
}

export function subscribeDemoUserChanged(handler) {
  if (typeof window === "undefined") {
    return () => {};
  }

  const wrappedHandler = (event) => {
    handler(event.detail?.userId || getSelectedDemoUserId());
  };

  window.addEventListener(DEMO_USER_CHANGED_EVENT, wrappedHandler);
  return () => window.removeEventListener(DEMO_USER_CHANGED_EVENT, wrappedHandler);
}
