"use client";

import { useEffect, useRef, useState } from "react";

import { loadGoogleMaps } from "@/lib/google-maps-loader";

type Coordinate = { latitude: number; longitude: number };

interface MapInstance {
  fitBounds: (bounds: BoundsInstance, padding?: number) => void;
}

interface BoundsInstance {
  extend: (point: { lat: number; lng: number }) => void;
}

interface PolylineInstance {
  setMap: (map: MapInstance | null) => void;
}

interface CircleInstance {
  setMap: (map: MapInstance | null) => void;
}

interface MapsLibrary {
  Map: new (
    element: HTMLElement,
    options: { center: { lat: number; lng: number }; zoom: number; mapTypeControl: boolean; streetViewControl: boolean },
  ) => MapInstance;
  LatLngBounds: new () => BoundsInstance;
  Polyline: new (options: {
    path: { lat: number; lng: number }[];
    geodesic: boolean;
    strokeColor: string;
    strokeOpacity: number;
    strokeWeight: number;
    map: MapInstance;
  }) => PolylineInstance;
  Circle: new (options: {
    center: { lat: number; lng: number };
    radius: number;
    fillColor: string;
    fillOpacity: number;
    strokeColor: string;
    strokeOpacity: number;
    strokeWeight: number;
    map: MapInstance;
  }) => CircleInstance;
}

function decodePolyline(encoded: string): { lat: number; lng: number }[] {
  const points: { lat: number; lng: number }[] = [];
  let index = 0;
  let latitude = 0;
  let longitude = 0;

  while (index < encoded.length) {
    let shift = 0;
    let result = 0;
    let byte: number;
    do {
      if (index >= encoded.length) throw new Error("Invalid encoded polyline.");
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    latitude += result & 1 ? ~(result >> 1) : result >> 1;

    shift = 0;
    result = 0;
    do {
      if (index >= encoded.length) throw new Error("Invalid encoded polyline.");
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    longitude += result & 1 ? ~(result >> 1) : result >> 1;
    points.push({ lat: latitude / 1e5, lng: longitude / 1e5 });
  }
  return points;
}

export function RouteMap({
  encodedPolyline,
  origin,
  stops,
  label = "Collection route map",
}: {
  encodedPolyline: string | null;
  origin: Coordinate;
  stops: Coordinate[];
  label?: string;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">(
    encodedPolyline ? "loading" : "unavailable",
  );

  useEffect(() => {
    const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY?.trim();
    if (!apiKey || !encodedPolyline || !hostRef.current) {
      setStatus("unavailable");
      return;
    }
    let active = true;
    let polyline: PolylineInstance | null = null;
    void loadGoogleMaps(apiKey)
      .then((maps) => maps.importLibrary("maps"))
      .then((library) => {
        if (!active || !hostRef.current) return;
        const { Map, LatLngBounds, Polyline } = library as MapsLibrary;
        const path = decodePolyline(encodedPolyline);
        if (path.length < 2) throw new Error("Route geometry is incomplete.");
        const map = new Map(hostRef.current, {
          center: { lat: origin.latitude, lng: origin.longitude },
          zoom: 12,
          mapTypeControl: false,
          streetViewControl: false,
        });
        polyline = new Polyline({
          path,
          geodesic: true,
          strokeColor: "#143529",
          strokeOpacity: 0.95,
          strokeWeight: 5,
          map,
        });
        const bounds = new LatLngBounds();
        path.forEach((point) => bounds.extend(point));
        bounds.extend({ lat: origin.latitude, lng: origin.longitude });
        stops.forEach((stop) => bounds.extend({ lat: stop.latitude, lng: stop.longitude }));
        map.fitBounds(bounds, 42);
        setStatus("ready");
      })
      .catch(() => {
        if (active) setStatus("unavailable");
      });
    return () => {
      active = false;
      polyline?.setMap(null);
    };
  }, [encodedPolyline, origin.latitude, origin.longitude, stops]);

  return (
    <div className="space-y-2">
      <div
        ref={hostRef}
        role="img"
        aria-label={label}
        className="h-72 w-full overflow-hidden rounded-card border border-line bg-surface-muted"
      />
      <p className="text-xs text-muted" role="status">
        {status === "ready"
          ? "Route geometry loaded from the saved Google Routes result."
          : status === "loading"
            ? "Loading the saved route…"
            : "The saved route map is unavailable. No route is being inferred in the browser."}
      </p>
    </div>
  );
}

export function PickupPointMap({
  location,
  label = "Your confirmed pickup point",
}: {
  location: Coordinate;
  label?: string;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "unavailable">("loading");

  useEffect(() => {
    const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY?.trim();
    if (!apiKey || !hostRef.current) {
      setStatus("unavailable");
      return;
    }
    let active = true;
    let marker: CircleInstance | null = null;
    void loadGoogleMaps(apiKey)
      .then((maps) => maps.importLibrary("maps"))
      .then((library) => {
        if (!active || !hostRef.current) return;
        const { Map, Circle } = library as MapsLibrary;
        const center = { lat: location.latitude, lng: location.longitude };
        const map = new Map(hostRef.current, {
          center,
          zoom: 15,
          mapTypeControl: false,
          streetViewControl: false,
        });
        marker = new Circle({
          center,
          radius: 45,
          fillColor: "#e8a317",
          fillOpacity: 0.35,
          strokeColor: "#143529",
          strokeOpacity: 1,
          strokeWeight: 3,
          map,
        });
        setStatus("ready");
      })
      .catch(() => {
        if (active) setStatus("unavailable");
      });
    return () => {
      active = false;
      marker?.setMap(null);
    };
  }, [location.latitude, location.longitude]);

  return (
    <div className="space-y-2">
      <div
        ref={hostRef}
        role="img"
        aria-label={label}
        className="h-72 w-full overflow-hidden rounded-card border border-line bg-surface-muted"
      />
      <p className="text-xs text-muted" role="status">
        {status === "ready"
          ? "Your confirmed household pickup point is shown. Other households and the full NGO route are hidden."
          : status === "loading"
            ? "Loading your pickup point…"
            : "The pickup map is unavailable. No location is being inferred in the browser."}
      </p>
    </div>
  );
}
