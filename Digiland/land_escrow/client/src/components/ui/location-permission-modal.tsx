import React, { useEffect, useState } from 'react';
import { Compass, MapPin, X, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from './button.js';
import { Card } from './card.js';

interface LocationPermissionModalProps {
  onLocationUpdate?: (lat: number, lng: number) => void;
}

export function LocationPermissionModal({ onLocationUpdate }: LocationPermissionModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [status, setStatus] = useState<'idle' | 'requesting' | 'success' | 'denied'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    // Check if user has already made a location choice
    const geoChoice = localStorage.getItem('digiland_geo_choice');
    const existingLat = localStorage.getItem('digiland_user_lat');

    if (!geoChoice && !existingLat && 'geolocation' in navigator) {
      // Delay prompt slightly after load for optimal UX
      const timer = setTimeout(() => {
        setIsOpen(true);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleRequestLocation = () => {
    if (!('geolocation' in navigator)) {
      setErrorMessage('Geolocation is not supported by your browser.');
      setStatus('denied');
      return;
    }

    setStatus('requesting');
    setErrorMessage(null);

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const lat = position.coords.latitude;
        const lng = position.coords.longitude;

        localStorage.setItem('digiland_geo_choice', 'allowed');
        localStorage.setItem('digiland_user_lat', lat.toString());
        localStorage.setItem('digiland_user_lng', lng.toString());
        localStorage.setItem('digiland_geo_timestamp', Date.now().toString());

        setStatus('success');

        if (onLocationUpdate) {
          onLocationUpdate(lat, lng);
        }

        // Sync with backend if user profile endpoint is available
        try {
          const csrfToken = (document.querySelector('[name=csrfmiddlewaretoken]') as HTMLInputElement)?.value;
          await fetch('/api/v1/buyer-profile/', {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
            },
            body: JSON.stringify({
              last_location_lat: lat,
              last_location_lng: lng,
            }),
          });
        } catch {
          // Non-blocking sync
        }

        setTimeout(() => {
          setIsOpen(false);
        }, 1800);
      },
      (error) => {
        localStorage.setItem('digiland_geo_choice', 'denied');
        setStatus('denied');
        if (error.code === error.PERMISSION_DENIED) {
          setErrorMessage('Location permission was denied. You can still manually search parcels by location.');
        } else {
          setErrorMessage('Unable to retrieve location. You can select your region manually.');
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000, // 5 minutes cache
      }
    );
  };

  const handleDismiss = () => {
    localStorage.setItem('digiland_geo_choice', 'dismissed');
    setIsOpen(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center sm:p-6 bg-black/40 backdrop-blur-xs transition-opacity animate-fade-in">
      <Card className="relative w-full max-w-md overflow-hidden rounded-3xl border border-white/20 bg-white/95 p-6 shadow-2xl backdrop-blur-xl dark:border-gray-800 dark:bg-gray-900/95 sm:p-8">
        <button
          onClick={handleDismiss}
          className="absolute right-4 top-4 rounded-full p-2 text-muted-foreground hover:bg-muted transition-colors"
          aria-label="Close prompt"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex flex-col items-center text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400">
            {status === 'success' ? (
              <CheckCircle2 className="h-9 w-9 text-emerald-600 animate-bounce" />
            ) : status === 'denied' ? (
              <AlertCircle className="h-9 w-9 text-amber-500" />
            ) : (
              <Compass className="h-9 w-9 animate-spin-slow" />
            )}
          </div>

          <h3 className="mb-2 text-xl font-extrabold text-foreground">
            {status === 'success'
              ? 'Location Enabled!'
              : status === 'denied'
              ? 'Location Not Set'
              : 'Tailor Your Land Experience'}
          </h3>

          <p className="mb-6 text-sm text-muted-foreground leading-relaxed">
            {status === 'success' ? (
              'Your location has been saved. We are customizing land parcel recommendations, nearby agent matches, and local pricing insights for you!'
            ) : status === 'denied' ? (
              errorMessage || 'No problem! You can browse and filter parcels by County manually anytime.'
            ) : (
              'Allow Digiland to access your location via your browser to discover land parcels near you, match with nearby verified agents, and see relevant local market trends.'
            )}
          </p>

          {status === 'idle' || status === 'requesting' ? (
            <div className="flex w-full flex-col gap-3 sm:flex-row">
              <Button
                onClick={handleRequestLocation}
                disabled={status === 'requesting'}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl py-3 shadow-lg shadow-emerald-600/20"
              >
                {status === 'requesting' ? (
                  <span className="flex items-center justify-center gap-2">
                    <MapPin className="h-4 w-4 animate-ping" /> Requesting access...
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <MapPin className="h-4 w-4" /> Allow Location Access
                  </span>
                )}
              </Button>

              <Button
                onClick={handleDismiss}
                variant="outline"
                className="w-full rounded-xl border-border hover:bg-muted"
              >
                Not Now
              </Button>
            </div>
          ) : (
            <Button
              onClick={handleDismiss}
              variant="outline"
              className="w-full rounded-xl border-border hover:bg-muted font-semibold"
            >
              Close
            </Button>
          )}

          <div className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground/80">
            <ShieldCheckIcon className="h-3.5 w-3.5 text-emerald-600" />
            <span>Your location is only used to personalize your browsing experience.</span>
          </div>
        </div>
      </Card>
    </div>
  );
}

function ShieldCheckIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  );
}
