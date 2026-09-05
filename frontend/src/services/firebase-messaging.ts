import { getApp, getApps, initializeApp } from "firebase/app";
import { getMessaging, getToken, isSupported } from "firebase/messaging";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export async function getBrowserFcmToken(): Promise<string | null> {
  if (typeof window === "undefined" || !process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY) {
    return null;
  }
  if (Object.values(firebaseConfig).some((value) => !value)) return null;
  if (!(await isSupported())) return null;

  const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  const registration = await navigator.serviceWorker.register("/firebase-messaging-sw.js");
  return getToken(getMessaging(app), {
    vapidKey: process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY,
    serviceWorkerRegistration: registration,
  });
}
