import React, { useState } from 'react';
import { Badge } from '../ui/badge.js';
import { Button } from '../ui/button.js';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card.js';
import { Input } from '../ui/input.js';
import {
  Smartphone,
  CreditCard,
  Building2,
  Wallet,
  Shield,
  Check,
  Loader2,
} from 'lucide-react';
import { cn } from '../../lib/utils.js';

type PaymentMethod = 'mpesa' | 'stripe' | 'paystack' | 'bank_transfer' | 'escrow_wallet';

interface PaymentOption {
  id: PaymentMethod;
  label: string;
  description: string;
  icon: React.ReactNode;
  available: boolean;
  badge?: string;
}

interface PaymentMethodSelectorProps {
  totalAmount: string;
  phoneNumber?: string;
  mpesaEnabled?: boolean;
  stripeEnabled?: boolean;
  paystackEnabled?: boolean;
  bankTransferEnabled?: boolean;
  escrowWalletEnabled?: boolean;
  bankDetails?: {
    bank_name: string;
    account_name: string;
    account_number: string;
    branch: string;
  };
  onPaymentInitiate: (method: PaymentMethod, details: Record<string, string>) => void;
  loading?: boolean;
}

const kshFormatter = new Intl.NumberFormat('en-KE', { maximumFractionDigits: 0, minimumFractionDigits: 0 });
function money(value: string | number) {
  const parsed = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  return Number.isFinite(parsed) ? `KES ${kshFormatter.format(parsed)}` : `KES ${value}`;
}

export function PaymentMethodSelector({
  totalAmount,
  phoneNumber = '',
  mpesaEnabled = true,
  stripeEnabled = false,
  paystackEnabled = false,
  bankTransferEnabled = true,
  escrowWalletEnabled = false,
  bankDetails,
  onPaymentInitiate,
  loading = false,
}: PaymentMethodSelectorProps) {
  const [selectedMethod, setSelectedMethod] = useState<PaymentMethod | null>(null);
  const [mpesaPhone, setMpesaPhone] = useState(phoneNumber);
  const [stripeConfirmed, setStripeConfirmed] = useState(false);
  const [polling, setPolling] = useState(false);

  const options: PaymentOption[] = [
    {
      id: 'mpesa' as PaymentMethod,
      label: 'M-Pesa',
      description: 'Pay via M-Pesa STK Push. Enter your phone number and confirm on your device.',
      icon: <Smartphone className="h-5 w-5" />,
      available: mpesaEnabled,
      badge: 'Recommended',
    },
    {
      id: 'stripe' as PaymentMethod,
      label: 'Card Payment',
      description: 'Pay with Visa or Mastercard via Stripe secure checkout.',
      icon: <CreditCard className="h-5 w-5" />,
      available: stripeEnabled,
    },
    {
      id: 'paystack' as PaymentMethod,
      label: 'Paystack',
      description: 'Pay via Paystack — supports mobile money and card payments.',
      icon: <CreditCard className="h-5 w-5" />,
      available: paystackEnabled,
    },
    {
      id: 'bank_transfer' as PaymentMethod,
      label: 'Bank Transfer',
      description: 'Transfer directly to the escrow bank account.',
      icon: <Building2 className="h-5 w-5" />,
      available: bankTransferEnabled,
    },
    {
      id: 'escrow_wallet' as PaymentMethod,
      label: 'Escrow Wallet',
      description: 'Pay from your Digiland escrow wallet balance.',
      icon: <Wallet className="h-5 w-5" />,
      available: escrowWalletEnabled,
    },
  ].filter(o => o.available);

  function handleConfirm() {
    if (!selectedMethod) return;
    const details: Record<string, string> = {};
    if (selectedMethod === 'mpesa') details.phone_number = mpesaPhone;
    onPaymentInitiate(selectedMethod, details);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-sm font-bold uppercase tracking-[0.24em] text-emerald-700">Payment Method</div>
          <p className="mt-1 text-sm text-muted-foreground">Choose how you want to pay {money(totalAmount)}.</p>
        </div>
        <Badge tone="outline">Secure</Badge>
      </div>

      <div className="space-y-3">
        {options.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => setSelectedMethod(option.id)}
            className={cn(
              'w-full rounded-2xl border p-4 text-left transition-all',
              selectedMethod === option.id
                ? 'border-emerald-300 bg-emerald-50/70 ring-2 ring-emerald-500'
                : 'border-border bg-white hover:border-emerald-200 hover:bg-emerald-50/30'
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-xl',
                  selectedMethod === option.id ? 'bg-emerald-100 text-emerald-700' : 'bg-muted text-muted-foreground'
                )}>
                  {option.icon}
                </div>
                <div>
                  <div className="font-semibold text-foreground">{option.label}</div>
                  <div className="text-xs text-muted-foreground">{option.description}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {option.badge && <Badge tone="success">{option.badge}</Badge>}
                <div className={cn(
                  'flex h-5 w-5 items-center justify-center rounded-full border-2',
                  selectedMethod === option.id ? 'border-emerald-600 bg-emerald-600' : 'border-border'
                )}>
                  {selectedMethod === option.id && <Check className="h-3 w-3 text-white" />}
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Method-specific UI */}
      {selectedMethod === 'mpesa' && (
        <Card className="border-emerald-200 bg-emerald-50/50">
          <CardContent className="p-4">
            <label className="mb-2 block text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground">M-Pesa Phone Number</label>
            <Input
              type="tel"
              placeholder="+254712345678"
              value={mpesaPhone}
              onChange={(e) => setMpesaPhone(e.target.value)}
            />
            <p className="mt-2 text-xs text-muted-foreground">An STK Push will be sent to this number. Confirm on your phone.</p>
          </CardContent>
        </Card>
      )}

      {selectedMethod === 'bank_transfer' && bankDetails && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardContent className="p-4 space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-blue-700">
              <Building2 className="h-4 w-4" /> Escrow Bank Account
            </div>
            <div className="space-y-1 text-sm">
              <div><span className="font-semibold">Bank:</span> {bankDetails.bank_name}</div>
              <div><span className="font-semibold">Account Name:</span> {bankDetails.account_name}</div>
              <div><span className="font-semibold">Account Number:</span> {bankDetails.account_number}</div>
              <div><span className="font-semibold">Branch:</span> {bankDetails.branch}</div>
            </div>
            <p className="text-xs text-muted-foreground">Transfer the exact amount and upload proof of payment.</p>
          </CardContent>
        </Card>
      )}

      {selectedMethod === 'stripe' && (
        <Card className="border-purple-200 bg-purple-50/50">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Shield className="h-4 w-4 text-purple-600" />
              You will be redirected to Stripe's secure checkout to complete payment.
            </div>
          </CardContent>
        </Card>
      )}

      {/* Confirm Button */}
      {selectedMethod && (
        <Button
          className="w-full rounded-full bg-emerald-700 hover:bg-emerald-800"
          size="lg"
          onClick={handleConfirm}
          disabled={loading || (selectedMethod === 'mpesa' && !mpesaPhone)}
        >
          {loading || polling ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              {polling ? 'Waiting for confirmation...' : 'Processing...'}
            </>
          ) : (
            <>Pay {money(totalAmount)} with {options.find(o => o.id === selectedMethod)?.label}</>
          )}
        </Button>
      )}
    </div>
  );
}
