"use client";

import { useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";

export interface SelectedLocation {
  address: string;
  lat?: number;
  lng?: number;
  place_id?: string;
}

interface LocationAutocompleteProps {
  onLocationSelected: (location: SelectedLocation) => void;
  defaultValue?: string;
  disabled?: boolean;
}

const MAPS_API_KEY =
  process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ||
  "AIzaSyCyCLm4ERLVT3HnwYHNGiz14K4E51jkahQ";

export function LocationAutocomplete({
  onLocationSelected,
  defaultValue = "",
  disabled = false,
}: LocationAutocompleteProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [address, setAddress] = useState(defaultValue);
  const [mapsLoaded, setMapsLoaded] = useState(false);
  const autocompleteRef = useRef<any>(null);

  useEffect(() => {
    let active = true;
    const scriptId = "google-maps-places-script";

    const initAutocomplete = () => {
      if (!window.google?.maps?.places || !inputRef.current || !active) return;
      try {
        const autocomplete = new window.google.maps.places.Autocomplete(
          inputRef.current,
          {
            fields: ["formatted_address", "geometry", "place_id", "name"],
          },
        );

        autocomplete.addListener("place_changed", () => {
          const place = autocomplete.getPlace();
          const chosenAddress =
            place.formatted_address || place.name || inputRef.current?.value || "";
          const lat = place.geometry?.location?.lat?.();
          const lng = place.geometry?.location?.lng?.();
          const place_id = place.place_id;

          setAddress(chosenAddress);
          onLocationSelected({
            address: chosenAddress,
            lat,
            lng,
            place_id,
          });
        });

        autocompleteRef.current = autocomplete;
        setMapsLoaded(true);
      } catch (err) {
        // Fallback gracefully to standard text input
      }
    };

    if (window.google?.maps?.places) {
      initAutocomplete();
      return;
    }

    let script = document.getElementById(scriptId) as HTMLScriptElement | null;
    if (!script) {
      script = document.createElement("script");
      script.id = scriptId;
      script.src = `https://maps.googleapis.com/maps/api/js?key=${MAPS_API_KEY}&libraries=places`;
      script.async = true;
      script.defer = true;
      script.onload = () => {
        initAutocomplete();
      };
      document.head.appendChild(script);
    } else {
      script.addEventListener("load", initAutocomplete);
    }

    return () => {
      active = false;
    };
  }, [onLocationSelected]);

  return (
    <div className="space-y-1">
      <label htmlFor="household-location-input" className="block text-xs font-semibold text-primary">
        Household address / location
      </label>
      <Input
        id="household-location-input"
        ref={inputRef}
        type="text"
        placeholder={mapsLoaded ? "Start typing address for suggestions…" : "Enter household location"}
        value={address}
        onChange={(e) => {
          setAddress(e.target.value);
          onLocationSelected({ address: e.target.value });
        }}
        disabled={disabled}
        className="bg-surface-muted text-sm"
        autoComplete="off"
      />
      <p className="text-[11px] text-muted">
        {mapsLoaded
          ? "Powered by Google Maps autocomplete"
          : "Type your address or area to pin your household location."}
      </p>
    </div>
  );
}

declare global {
  interface Window {
    google?: any;
  }
}
