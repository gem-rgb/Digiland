import React, { useEffect, useRef, useState, useCallback } from 'react';
import { MapPin, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils.js';
import type { ParcelSummary } from '../../types.js';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface MapParcel extends Pick<ParcelSummary, 'parcel_number' | 'county' | 'constituency' | 'ward' | 'land_size' | 'land_use_type' | 'verification_status' | 'displayed_price' | 'asking_price' | 'details_url' | 'image_url'> {
  lat: number;
  lng: number;
  match_score?: number;
}

export interface LandMapProps {
  /** Array of parcels with lat/lng coordinates */
  parcels: MapParcel[];
  /** Currently selected parcel number */
  selectedParcel?: string | null;
  /** Callback when a parcel marker is clicked */
  onParcelSelect?: (parcel: MapParcel) => void;
  /** Map container height (default: 400px) */
  height?: string | number;
  /** Center coordinates [lat, lng] */
  center?: [number, number];
  /** Default zoom level (default: 7) */
  zoom?: number;
  /** Optional county/region polygons to highlight */
  countyHighlights?: Array<{
    name: string;
    coordinates: [number, number][][];
    color?: string;
  }>;
  /** Additional CSS class */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  CDN Loading Helpers                                                */
/* ------------------------------------------------------------------ */

const LEAFLET_CSS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
const LEAFLET_JS = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
const MARKERCLUSTER_CSS = 'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css';
const MARKERCLUSTER_DEFAULT_CSS = 'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css';
const MARKERCLUSTER_JS = 'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js';

let loadPromise: Promise<void> | null = null;

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

function loadStylesheet(href: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`link[href="${href}"]`)) {
      resolve();
      return;
    }
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    link.onload = () => resolve();
    link.onerror = () => reject(new Error(`Failed to load ${href}`));
    document.head.appendChild(link);
  });
}

function loadLeaflet(): Promise<void> {
  if (loadPromise) return loadPromise;
  loadPromise = Promise.all([
    loadStylesheet(LEAFLET_CSS),
    loadStylesheet(MARKERCLUSTER_CSS),
    loadStylesheet(MARKERCLUSTER_DEFAULT_CSS),
    loadScript(LEAFLET_JS),
  ])
    .then(() => loadScript(MARKERCLUSTER_JS))
    .then(() => {
      // Define custom emerald marker icon
      const L = (window as any).L;
      if (L) {
        const emeraldIcon = L.divIcon({
          html: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="28" height="42">
            <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24C24 5.4 18.6 0 12 0z" fill="#059669" stroke="#065f46" stroke-width="1"/>
            <circle cx="12" cy="12" r="5" fill="#d1fae5"/>
          </svg>`,
          className: 'digiland-marker-icon',
          iconSize: [28, 42],
          iconAnchor: [14, 42],
          popupAnchor: [0, -42],
        });

        const selectedIcon = L.divIcon({
          html: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="34" height="50">
            <path d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24C24 5.4 18.6 0 12 0z" fill="#047857" stroke="#064e3b" stroke-width="1.5"/>
            <circle cx="12" cy="12" r="5" fill="#6ee7b7"/>
          </svg>`,
          className: 'digiland-marker-icon digiland-marker-icon--selected',
          iconSize: [34, 50],
          iconAnchor: [17, 50],
          popupAnchor: [0, -50],
        });

        (window as any).__digiland_map_icons = { emeraldIcon, selectedIcon };
      }
    });
  return loadPromise;
}

/* ------------------------------------------------------------------ */
/*  Kenya Default Center                                               */
/* ------------------------------------------------------------------ */

const KENYA_CENTER: [number, number] = [-0.0236, 37.9062];
const DEFAULT_ZOOM = 7;

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function LandMap({
  parcels,
  selectedParcel = null,
  onParcelSelect,
  height = 400,
  center = KENYA_CENTER,
  zoom = DEFAULT_ZOOM,
  countyHighlights = [],
  className,
}: LandMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const clusterRef = useRef<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const heightStyle = typeof height === 'number' ? `${height}px` : height;

  // Initialize map
  useEffect(() => {
    if (!containerRef.current) return;

    let cancelled = false;

    loadLeaflet()
      .then(() => {
        if (cancelled || !containerRef.current) return;

        const L = (window as any).L;
        if (!L) {
          setError('Leaflet failed to load');
          setLoading(false);
          return;
        }

        const map = L.map(containerRef.current, {
          center,
          zoom,
          scrollWheelZoom: true,
          zoomControl: true,
        });

        // Tile layer - using a clean, green-friendly style
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 18,
        }).addTo(map);

        // Marker cluster group
        const clusterGroup = L.markerClusterGroup({
          maxClusterRadius: 50,
          spiderfyOnMaxZoom: true,
          showCoverageOnHover: false,
          iconCreateFunction: (cluster: any) => {
            const count = cluster.getChildCount();
            let size = 'small';
            let dim = 40;
            if (count > 100) { size = 'large'; dim = 56; }
            else if (count > 10) { size = 'medium'; dim = 48; }
            return L.divIcon({
              html: `<div class="digiland-cluster digiland-cluster--${size}"><span>${count}</span></div>`,
              className: 'digiland-cluster-wrapper',
              iconSize: L.point(dim, dim),
            });
          },
        });

        clusterGroup.addTo(map);
        clusterRef.current = clusterGroup;
        mapInstanceRef.current = map;

        setLoading(false);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message || 'Failed to load map');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
    // Only re-init when center/zoom changes (rare)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update markers when parcels change
  useEffect(() => {
    const L = (window as any).L;
    const map = mapInstanceRef.current;
    const cluster = clusterRef.current;
    if (!L || !map || !cluster) return;

    const icons = (window as any).__digiland_map_icons || {};
    const defaultIcon = icons.emeraldIcon || new L.Icon.Default();
    const selIcon = icons.selectedIcon || new L.Icon.Default();

    // Clear existing markers
    cluster.clearLayers();
    markersRef.current = [];

    parcels.forEach((parcel) => {
      if (parcel.lat == null || parcel.lng == null) return;

      const isSelected = selectedParcel === parcel.parcel_number;
      const marker = L.marker([parcel.lat, parcel.lng], {
        icon: isSelected ? selIcon : defaultIcon,
      });

      // Build popup content
      const price = parcel.displayed_price || parcel.asking_price;
      const popupContent = `
        <div class="digiland-popup">
          ${parcel.image_url ? `<img src="${parcel.image_url}" alt="${parcel.parcel_number}" class="digiland-popup__image" />` : ''}
          <div class="digiland-popup__content">
            <div class="digiland-popup__title">${parcel.parcel_number}</div>
            <div class="digiland-popup__location">${parcel.county}, ${parcel.constituency}${parcel.ward ? ` &middot; ${parcel.ward}` : ''}</div>
            <div class="digiland-popup__meta">
              <span>${parcel.land_use_type}</span>
              <span>&middot;</span>
              <span>${parcel.land_size}</span>
            </div>
            ${price ? `<div class="digiland-popup__price">KES ${price}</div>` : ''}
            ${parcel.match_score != null ? `<div class="digiland-popup__match">${Math.round(parcel.match_score)}% match</div>` : ''}
          </div>
        </div>
      `;

      marker.bindPopup(popupContent, {
        maxWidth: 260,
        className: 'digiland-popup-container',
      });

      marker.on('click', () => {
        if (onParcelSelect) {
          onParcelSelect(parcel);
        }
      });

      cluster.addLayer(marker);
      markersRef.current.push({ marker, parcel });
    });

    // Fit bounds if we have parcels
    if (parcels.length > 0) {
      const group = L.featureGroup(markersRef.current.map((m: any) => m.marker));
      if (group.getLayers().length > 0) {
        map.fitBounds(group.getBounds().pad(0.1), { maxZoom: 14 });
      }
    }
  }, [parcels, selectedParcel, onParcelSelect]);

  // Update county highlights
  useEffect(() => {
    const L = (window as any).L;
    const map = mapInstanceRef.current;
    if (!L || !map || !countyHighlights.length) return;

    const layers: any[] = [];

    countyHighlights.forEach((county) => {
      const polygon = L.polygon(county.coordinates, {
        color: county.color || '#059669',
        weight: 2,
        opacity: 0.7,
        fillColor: county.color || '#059669',
        fillOpacity: 0.08,
        dashArray: '6 4',
      }).addTo(map);

      polygon.bindTooltip(county.name, {
        sticky: true,
        className: 'digiland-county-tooltip',
      });

      layers.push(polygon);
    });

    return () => {
      layers.forEach((layer) => map.removeLayer(layer));
    };
  }, [countyHighlights]);

  // Fly to selected parcel
  useEffect(() => {
    if (!selectedParcel || !mapInstanceRef.current) return;

    const found = markersRef.current.find(
      (m: any) => m.parcel.parcel_number === selectedParcel
    );
    if (found) {
      mapInstanceRef.current.flyTo(
        [found.parcel.lat, found.parcel.lng],
        14,
        { duration: 0.8 }
      );
      found.marker.openPopup();
    }
  }, [selectedParcel]);

  return (
    <div className={cn('relative w-full overflow-hidden rounded-3xl border border-border/70', className)}>
      {loading && (
        <div
          className="flex items-center justify-center bg-muted/30"
          style={{ height: heightStyle }}
        >
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
            <span className="text-sm font-medium">Loading map…</span>
          </div>
        </div>
      )}
      {error && (
        <div
          className="flex items-center justify-center bg-muted/30"
          style={{ height: heightStyle }}
        >
          <div className="flex flex-col items-center gap-3 text-center text-muted-foreground">
            <MapPin className="h-8 w-8 text-muted-foreground" />
            <span className="text-sm font-medium">Map unavailable</span>
            <span className="text-xs">{error}</span>
          </div>
        </div>
      )}
      <div
        ref={containerRef}
        className="digiland-map-container"
        style={{ height: heightStyle, width: '100%' }}
      />
      {parcels.length > 0 && !loading && !error && (
        <div className="absolute bottom-3 left-3 rounded-full bg-white/90 px-3 py-1.5 text-xs font-semibold text-muted-foreground shadow-sm backdrop-blur-sm dark:bg-slate-800/90 dark:text-slate-300">
          {parcels.length} parcel{parcels.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}

export default LandMap;
