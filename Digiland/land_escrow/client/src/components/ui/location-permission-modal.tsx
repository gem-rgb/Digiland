import React, { useEffect, useState } from 'react';
import { Compass, MapPin, X, CheckCircle2, AlertCircle } from 'lucide-react';
import { Button } from './button.js';
import { Card } from './card.js';

interface LocationPermissionModalProps {
  onLocationUpdate?: (lat: number, lng: number) => void;
}

const KENYAN_COUNTIES = [
  'Nairobi', 'Mombasa', 'Kiambu', 'Nakuru', 'Kajiado', 'Machakos', 'Kilifi', 'Uasin Gishu',
  'Kisumu', 'Nyeri', 'Laikipia', 'Narok', 'Kericho', 'Trans Nzoia', 'Murang\'a', 'Meru',
  'Bomet', 'Kakamega', 'Bungoma', 'Kwale', 'Taita Taveta', 'Embu', 'Kitui', 'Makueni',
  'Nyandarua', 'Kisii', 'Homa Bay', 'Siaya', 'Migori', 'Kirinyaga', 'Nandi', 'Vihiga',
  'Busia', 'Baringo', 'Elgeyo Marakwet', 'West Pokot', 'Turkana', 'Samburu', 'Isiolo',
  'Marsabit', 'Tharaka Nithi', 'Garissa', 'Wajir', 'Mandera', 'Tana River', 'Lamu'
];

export function LocationPermissionModal({ onLocationUpdate }: LocationPermissionModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [status, setStatus] = useState<'idle' | 'requesting' | 'success' | 'denied'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [selectedCounty, setSelectedCounty] = useState<string>('');

  useEffect(() => {
    // Check if user has already made a location choice
    const geoChoice = localStorage.getItem('digiland_geo_choice');
    const existingLat = localStorage.getItem('digiland_user_lat');
    const existingCounty = localStorage.getItem('digiland_user_county');

    if (!geoChoice && !existingLat && !existingCounty && 'geolocation' in navigator) {
      // Delay prompt slightly after load for optimal UX
      const timer = setTimeout(() => {
        setIsOpen(true);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleRequestLocation = () => {
    if (!('geolocation' in navigator)) {
      setErrorMessage('Geolocation is not supported by your browser. Please select your County manually below.');
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
          setErrorMessage('Location permission was denied. You can select your County manually below.');
        } else {
          setErrorMessage('Unable to retrieve automatic location. Select your County manually below to personalize listings.');
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000, // 5 minutes cache
      }
    );
  };

  const handleSelectCounty = (county: string) => {
    if (!county) return;
    setSelectedCounty(county);
    localStorage.setItem('digiland_geo_choice', 'manual');
    localStorage.setItem('digiland_user_county', county);

    setStatus('success');
    setErrorMessage(null);

    setTimeout(() => {
      setIsOpen(false);
      window.location.href = `/parcels/?q=${encodeURIComponent(county)}`;
    }, 1200);
  };

  const handleDismiss = () => {
    localStorage.setItem('digiland_geo_choice', 'dismissed');
    setIsOpen(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center sm:p-6 bg-black/50 backdrop-blur-xs transition-opacity animate-fade-in">
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
              ? selectedCounty ? `Region set to ${selectedCounty}!` : 'Location Enabled!'
              : status === 'denied'
              ? 'Select Region Manually'
              : 'Tailor Your Land Experience'}
          </h3>

          <p className="mb-5 text-sm text-muted-foreground leading-relaxed">
            {status === 'success' ? (
              selectedCounty
                ? `Showing verified parcels and nearby agent matches in ${selectedCounty}...`
                : 'Your location has been saved. We are customizing land parcel recommendations for you!'
            ) : status === 'denied' ? (
              errorMessage || 'Select your operating or target County to customize land listings.'
            ) : (
              'Allow Digiland to access your location via your browser to discover land parcels near you, match with nearby verified agents, and see local market trends.'
            )}
          </p>

          {/* Manual County Selector Dropdown */}
          {status === 'denied' && (
            <div className="w-full space-y-3 mb-4">
              <div className="relative">
                <select
                  value={selectedCounty}
                  onChange={(e) => handleSelectCounty(e.target.value)}
                  className="w-full appearance-none rounded-2xl border border-emerald-500/40 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none cursor-pointer"
                >
                  <option value="">-- Choose Your County --</option>
                  {KENYAN_COUNTIES.map((c) => (
                    <option key={c} value={c}>{c} County</option>
                  ))}
                </select>
                <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-500">
                  ▼
                </div>
              </div>
            </div>
          )}

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
                onClick={() => setStatus('denied')}
                className="w-full rounded-xl border border-slate-300 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold py-3 shadow-xs transition-colors"
              >
                Select County Manually
              </Button>
            </div>
          ) : (
            <Button
              onClick={handleDismiss}
              className="w-full rounded-xl border border-slate-300 bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold py-3 shadow-xs transition-colors"
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
