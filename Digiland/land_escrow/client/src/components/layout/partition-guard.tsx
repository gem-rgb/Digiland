import React from 'react';
import { ShieldAlert, ArrowRight, Lock, ExternalLink } from 'lucide-react';
import { Button } from '../ui/button.js';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card.js';
import { requiredPartitionForRole, getPortalUrl, type Partition } from '../../lib/partition-context.js';

interface PartitionGuardProps {
  userRole: string;
  currentPartition: Partition;
  onSwitchPortal?: (targetPartition: Partition) => void;
}

export const PartitionGuard: React.FC<PartitionGuardProps> = ({
  userRole,
  currentPartition,
  onSwitchPortal,
}) => {
  const targetPartition = requiredPartitionForRole(userRole);
  const targetUrl = getPortalUrl(targetPartition);

  const partitionNames: Record<Partition, string> = {
    marketing: 'Marketing Portal (digiland.co.ke)',
    app: 'Buyer & Seller App (app.digiland.co.ke)',
    staff: 'Staff Security Desk (staff.digiland.co.ke)',
    admin: 'Admin Control Plane (admin.digiland.co.ke)',
  };

  const handleRedirect = () => {
    if (onSwitchPortal) {
      onSwitchPortal(targetPartition);
    } else {
      window.location.href = targetUrl;
    }
  };

  return (
    <div className="min-h-[70vh] flex items-center justify-center p-6 bg-slate-900/90 text-white">
      <Card className="max-w-lg w-full bg-slate-950 border-emerald-500/30 shadow-2xl shadow-emerald-950/50 text-slate-100">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mb-3">
            <ShieldAlert className="w-8 h-8 text-amber-400" />
          </div>
          <CardTitle className="text-2xl font-extrabold text-white tracking-tight">
            Partition Access Restricted
          </CardTitle>
          <CardDescription className="text-slate-400 mt-2 text-sm">
            Your account role <span className="font-semibold text-emerald-400">"{userRole}"</span> is not authorized to access the{' '}
            <span className="font-semibold text-amber-300">{partitionNames[currentPartition]}</span>.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 pt-2">
          <div className="rounded-xl bg-slate-900/80 border border-slate-800 p-4 space-y-3 text-sm text-slate-300">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold">
              <Lock className="w-4 h-4" /> Digiland Partition Security Policy
            </div>
            <p className="text-xs leading-relaxed text-slate-400">
              Digiland separates user roles into dedicated security partitions. Agents and Lawyers must use the Staff Portal, while Buyers and Sellers access the App Portal.
            </p>
            <div className="pt-2 border-t border-slate-800 flex justify-between items-center text-xs">
              <span className="text-slate-500">Your Target Portal:</span>
              <span className="font-mono text-purple-400 font-bold">{partitionNames[targetPartition]}</span>
            </div>
          </div>

          <Button
            onClick={handleRedirect}
            className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-emerald-900/40"
          >
            <span>Proceed to {partitionNames[targetPartition].split('(')[0].trim()}</span>
            <ArrowRight className="w-4 h-4" />
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};
