"use client";

import { useEffect, useRef, useState } from "react";
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
  toPlace: () => GooglePlace;
}

interface PlacePredictionSelectEvent extends Event {
  placePrediction: PlacePrediction;
}

interface PlaceAutocompleteElement extends HTMLElement {
  disabled: boolean;
  placeholder: string;
  value: string;
}

interface PlacesLibrary {
  PlaceAutocompleteElement: new () => PlaceAutocompleteElement;
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
  const widgetHostRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<PlaceAutocompleteElement | null>(null);
  const selectedCallbackRef = useRef(onLocationSelected);
  const disabledRef = useRef(disabled);
  const addressRef = useRef(defaultValue);
  const [address, setAddress] = useState(defaultValue);
  const [mapsStatus, setMapsStatus] = useState<MapsStatus>(
    MAPS_API_KEY ? "loading" : "unavailable",
  );

  useEffect(() => {
    selectedCallbackRef.current = onLocationSelected;
  }, [onLocationSelected]);

  useEffect(() => {
    disabledRef.current = disabled;
    if (widgetRef.current) widgetRef.current.disabled = disabled;
  }, [disabled]);

  useEffect(() => {
    if (!MAPS_API_KEY) return;

    let active = true;
    let failed = false;
    let detachWidgetListeners: (() => void) | undefined;
    const previousAuthFailure = window.gm_authFailure;
    const markUnavailable = () => {
      if (!active) return;
      failed = true;
      detachWidgetListeners?.();
      widgetRef.current?.remove();
      widgetRef.current = null;
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
        const { PlaceAutocompleteElement } = library as PlacesLibrary;
        if (!active || failed || !widgetHostRef.current) return;

        const widget = new PlaceAutocompleteElement();
        widget.id = `${idPrefix}-autocomplete`;
        widget.className = "ecoloop-place-autocomplete";
        widget.placeholder = "Start typing an address or area…";
        widget.value = addressRef.current;
        widget.disabled = disabledRef.current;
        widget.setAttribute("maxlength", "256");
        widget.setAttribute("aria-labelledby", `${idPrefix}-label`);
        widget.setAttribute("aria-describedby", `${idPrefix}-help`);

        const handleInput = () => {
          const nextAddress = widget.value;
          addressRef.current = nextAddress;
          setAddress(nextAddress);
          selectedCallbackRef.current({ address: nextAddress });
        };
        const handleSelection = async (event: Event) => {
          try {
            const place = (event as PlacePredictionSelectEvent).placePrediction.toPlace();
            await place.fetchFields({
              fields: ["id", "displayName", "formattedAddress", "location"],
            });
            if (!active) return;

            const chosenAddress =
              place.formattedAddress || place.displayName || widget.value || "";
            const lat = place.location?.lat();
            const lng = place.location?.lng();

            widget.value = chosenAddress;
            addressRef.current = chosenAddress;
            setAddress(chosenAddress);
            selectedCallbackRef.current({
              address: chosenAddress,
              lat,
              lng,
              place_id: place.id,
            });
          } catch {
            markUnavailable();
          }
        };

        widget.addEventListener("input", handleInput);
        widget.addEventListener("gmp-select", handleSelection);
        widget.addEventListener("gmp-error", markUnavailable);
        detachWidgetListeners = () => {
          widget.removeEventListener("input", handleInput);
          widget.removeEventListener("gmp-select", handleSelection);
          widget.removeEventListener("gmp-error", markUnavailable);
        };
        widgetHostRef.current.replaceChildren(widget);
        widgetRef.current = widget;
        setMapsStatus("ready");
      })
      .catch(markUnavailable);

    return () => {
      active = false;
      detachWidgetListeners?.();
      widgetRef.current?.remove();
      widgetRef.current = null;
      if (window.gm_authFailure === authFailure) {
        window.gm_authFailure = previousAuthFailure;
      }
    };
  }, [idPrefix]);

  const updateFallbackAddress = (nextAddress: string) => {
    addressRef.current = nextAddress;
    setAddress(nextAddress);
    selectedCallbackRef.current({ address: nextAddress });
  };

  return (
    <div className="space-y-1">
      <label
        id={`${idPrefix}-label`}
        htmlFor={mapsStatus === "ready" ? `${idPrefix}-autocomplete` : `${idPrefix}-input`}
        className="block text-xs font-semibold text-primary"
      >
        {label}
      </label>
      <div ref={widgetHostRef} hidden={mapsStatus !== "ready"} />
      {mapsStatus !== "ready" && (
        <Input
          id={`${idPrefix}-input`}
          type="text"
          placeholder="Enter household address or area"
          value={address}
          onChange={(event) => updateFallbackAddress(event.target.value)}
          disabled={disabled}
          className="bg-surface-muted text-sm"
          autoComplete="street-address"
          maxLength={256}
          aria-describedby={`${idPrefix}-help`}
        />
      )}
      <p id={`${idPrefix}-help`} role="status" className="text-[11px] text-muted">
        {mapsStatus === "ready"
          ? "Choose a Google Maps suggestion to save its address and map location."
          : mapsStatus === "loading"
            ? "Loading Google Maps address suggestions…"
            : "Google Maps suggestions are unavailable. You can still enter the location manually."}
      </p>
    </div>
  );
}
