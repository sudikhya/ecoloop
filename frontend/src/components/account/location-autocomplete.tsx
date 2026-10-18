"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Input } from "@/components/ui/input";
import { loadGoogleMaps } from "@/lib/google-maps-loader";

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
  idPrefix?: string;
  label?: string;
}

interface MapsLatLng {
  lat: () => number;
  lng: () => number;
}

interface GooglePlace {
  displayName?: string | null;
  fetchFields: (options: { fields: string[] }) => Promise<void>;
  formattedAddress?: string | null;
  id?: string;
  location?: MapsLatLng | null;
}

interface PlacePrediction {
  text: { toString: () => string };
  toPlace: () => GooglePlace;
}

type AutocompleteSessionToken = object;

interface PlacesLibrary {
  AutocompleteSessionToken: new () => AutocompleteSessionToken;
  AutocompleteSuggestion: {
    fetchAutocompleteSuggestions: (request: {
      input: string;
      sessionToken: AutocompleteSessionToken;
    }) => Promise<{ suggestions: { placePrediction?: PlacePrediction }[] }>;
  };
}

type MapsStatus = "loading" | "ready" | "unavailable";

const MAPS_API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;

export function LocationAutocomplete({
  onLocationSelected,
  defaultValue = "",
  disabled = false,
  idPrefix = "household-location",
  label = "Household address / location",
}: LocationAutocompleteProps) {
  const selectedCallbackRef = useRef(onLocationSelected);
  const placesRef = useRef<PlacesLibrary | null>(null);
  const sessionTokenRef = useRef<AutocompleteSessionToken | null>(null);
  const requestIdRef = useRef(0);
  const confirmedAddressRef = useRef(defaultValue);
  const [address, setAddress] = useState(defaultValue);
  const [suggestions, setSuggestions] = useState<PlacePrediction[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [searching, setSearching] = useState(false);
  const [mapsStatus, setMapsStatus] = useState<MapsStatus>(
    MAPS_API_KEY ? "loading" : "unavailable",
  );

  useEffect(() => {
    selectedCallbackRef.current = onLocationSelected;
  }, [onLocationSelected]);

  useEffect(() => {
    if (!MAPS_API_KEY) return;

    let active = true;
    const previousAuthFailure = window.gm_authFailure;
    const markUnavailable = () => {
      if (!active) return;
      requestIdRef.current += 1;
      placesRef.current = null;
      sessionTokenRef.current = null;
      setSuggestions([]);
      setSearching(false);
      setMapsStatus("unavailable");
    };
    const authFailure = () => {
      previousAuthFailure?.();
      markUnavailable();
    };
    window.gm_authFailure = authFailure;

    void loadGoogleMaps(MAPS_API_KEY)
      .then((maps) => maps.importLibrary("places"))
      .then((library) => {
        if (!active) return;
        const places = library as PlacesLibrary;
        if (
          typeof places.AutocompleteSuggestion?.fetchAutocompleteSuggestions !== "function" ||
          typeof places.AutocompleteSessionToken !== "function"
        ) {
          markUnavailable();
          return;
        }
        placesRef.current = places;
        sessionTokenRef.current = new places.AutocompleteSessionToken();
        setMapsStatus("ready");
      })
      .catch(markUnavailable);

    return () => {
      active = false;
      requestIdRef.current += 1;
      if (window.gm_authFailure === authFailure) {
        window.gm_authFailure = previousAuthFailure;
      }
    };
  }, []);

  useEffect(() => {
    const places = placesRef.current;
    const query = address.trim();
    if (
      mapsStatus !== "ready" ||
      !places ||
      query.length < 3 ||
      query === confirmedAddressRef.current
    ) {
      setSearching(false);
      setSuggestions([]);
      setActiveIndex(-1);
      return;
    }

    const requestId = ++requestIdRef.current;
    setSearching(true);
    const timer = window.setTimeout(() => {
      sessionTokenRef.current ??= new places.AutocompleteSessionToken();
      void places.AutocompleteSuggestion.fetchAutocompleteSuggestions({
        input: query,
        sessionToken: sessionTokenRef.current,
      })
        .then(({ suggestions: nextSuggestions }) => {
          if (requestId !== requestIdRef.current) return;
          setSuggestions(
            nextSuggestions
              .map((suggestion) => suggestion.placePrediction)
              .filter((prediction): prediction is PlacePrediction => Boolean(prediction))
              .slice(0, 6),
          );
          setActiveIndex(-1);
          setSearching(false);
        })
        .catch(() => {
          if (requestId !== requestIdRef.current) return;
          setSuggestions([]);
          setSearching(false);
          setMapsStatus("unavailable");
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
    };
  }, [address, mapsStatus]);

  const updateAddress = (nextAddress: string) => {
    confirmedAddressRef.current = "";
    setAddress(nextAddress);
    selectedCallbackRef.current({ address: nextAddress });
  };

  const chooseSuggestion = async (prediction: PlacePrediction) => {
    try {
      const place = prediction.toPlace();
      await place.fetchFields({
        fields: ["id", "displayName", "formattedAddress", "location"],
      });
      const chosenAddress = place.formattedAddress || place.displayName || prediction.text.toString();
      const lat = place.location?.lat();
      const lng = place.location?.lng();
      if (!chosenAddress || !Number.isFinite(lat) || !Number.isFinite(lng)) {
        throw new Error("The selected Google place has no mapped location.");
      }

      requestIdRef.current += 1;
      confirmedAddressRef.current = chosenAddress;
      setAddress(chosenAddress);
      setSuggestions([]);
      setActiveIndex(-1);
      sessionTokenRef.current = placesRef.current
        ? new placesRef.current.AutocompleteSessionToken()
        : null;
      selectedCallbackRef.current({
        address: chosenAddress,
        lat,
        lng,
        place_id: place.id,
      });
    } catch {
      setSuggestions([]);
      setMapsStatus("unavailable");
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (suggestions.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => (current + 1) % suggestions.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => (current <= 0 ? suggestions.length - 1 : current - 1));
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      void chooseSuggestion(suggestions[activeIndex]);
    } else if (event.key === "Escape") {
      setSuggestions([]);
      setActiveIndex(-1);
    }
  };

  const listboxId = `${idPrefix}-suggestions`;

  return (
    <div className="relative space-y-1">
      <label htmlFor={`${idPrefix}-input`} className="block text-xs font-semibold text-primary">
        {label}
      </label>
      <Input
        id={`${idPrefix}-input`}
        type="text"
        placeholder="Start typing an address or area…"
        value={address}
        onChange={(event) => updateAddress(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className="bg-surface-muted text-sm"
        autoComplete="off"
        maxLength={256}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={suggestions.length > 0}
        aria-controls={listboxId}
        aria-activedescendant={activeIndex >= 0 ? `${idPrefix}-suggestion-${activeIndex}` : undefined}
        aria-describedby={`${idPrefix}-help`}
      />
      {suggestions.length > 0 && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute inset-x-0 top-full z-[100] mt-1 max-h-72 overflow-y-auto rounded-2xl border border-line bg-white p-1 shadow-xl"
        >
          {suggestions.map((prediction, index) => {
            const suggestionLabel = prediction.text.toString();
            return (
              <li key={`${suggestionLabel}-${index}`} role="presentation">
                <button
                  id={`${idPrefix}-suggestion-${index}`}
                  type="button"
                  role="option"
                  aria-selected={index === activeIndex}
                  className={`min-h-11 w-full rounded-xl px-3 py-2 text-left text-sm text-foreground hover:bg-primary-soft focus:bg-primary-soft focus:outline-none ${
                    index === activeIndex ? "bg-primary-soft" : ""
                  }`}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => void chooseSuggestion(prediction)}
                >
                  {suggestionLabel}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <p id={`${idPrefix}-help`} role="status" className="text-[11px] text-muted">
        {mapsStatus === "unavailable"
          ? "Google Maps suggestions are unavailable. You can still enter the location manually."
          : mapsStatus === "loading"
            ? "Loading Google Maps address suggestions…"
            : searching
              ? "Finding matching Google Maps locations…"
              : suggestions.length > 0
                ? "Choose a Google Maps suggestion to save its address and map location."
                : "Enter at least three characters to search Google Maps."}
      </p>
    </div>
  );
}
