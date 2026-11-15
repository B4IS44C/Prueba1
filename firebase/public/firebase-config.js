// Pegue aquí la configuración web de su app (Consola Firebase → Configuración del proyecto → Tus apps → Web).
// Estos valores NO son secretos: identifican el proyecto; la seguridad la dan firestore.rules.
self.FIREBASE_CONFIG = {
  apiKey: "REEMPLAZAR",
  authDomain: "TU-PROYECTO.firebaseapp.com",
  projectId: "TU-PROYECTO",
  storageBucket: "TU-PROYECTO.appspot.com",
  messagingSenderId: "REEMPLAZAR",
  appId: "REEMPLAZAR",
};
// Consola Firebase → Configuración → Cloud Messaging → Certificados push web → Generar par de claves
self.VAPID_KEY = "REEMPLAZAR";
