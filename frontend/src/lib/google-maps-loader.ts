export interface GoogleMapsNamespace {
  importLibrary: (library: "places" | "maps") => Promise<unknown>;
}

const MAPS_SCRIPT_ID = "google-maps-platform-script";
const MAPS_READY_CALLBACK = "__ecoloopGoogleMapsReady";
let mapsLoaderPromise: Promise<GoogleMapsNamespace> | null = null;

export function loadGoogleMaps(apiKey: string): Promise<GoogleMapsNamespace> {
  if (window.google?.maps?.importLibrary) {
    return Promise.resolve(window.google.maps);
  }
  if (mapsLoaderPromise) return mapsLoaderPromise;

  mapsLoaderPromise = new Promise<GoogleMapsNamespace>((resolve, reject) => {
    const clearReadyCallback = () => {
      delete window.__ecoloopGoogleMapsReady;
    };
    const handleReady = () => {
      clearReadyCallback();
      if (window.google?.maps?.importLibrary) {
        resolve(window.google.maps);
      } else {
        reject(new Error("Google Maps loaded without the library importer."));
      }
    };
    const handleError = () => {
      clearReadyCallback();
      reject(new Error("Google Maps failed to load."));
    };

    document.getElementById(MAPS_SCRIPT_ID)?.remove();
    window.__ecoloopGoogleMapsReady = handleReady;
    const script = document.createElement("script");
    script.id = MAPS_SCRIPT_ID;
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&loading=async&libraries=places&v=weekly&auth_referrer_policy=origin&callback=${MAPS_READY_CALLBACK}`;
    script.async = true;
    script.addEventListener("error", handleError, { once: true });
    document.head.appendChild(script);
  }).catch((error: unknown) => {
    mapsLoaderPromise = null;
    throw error;
  });

  return mapsLoaderPromise;
}

declare global {
  interface Window {
    __ecoloopGoogleMapsReady?: () => void;
    gm_authFailure?: () => void;
    google?: {
      maps?: GoogleMapsNamespace;
    };
  }
}
