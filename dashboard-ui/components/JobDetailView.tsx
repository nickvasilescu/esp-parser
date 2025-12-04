import React from 'react';
import { Job } from '../data/mockData';
import StatusBadge from './StatusBadge';
import ProgressBar from './ProgressBar';
import { X, ExternalLink, FileText, Calculator, ShoppingCart, Globe, Clock } from 'lucide-react';
import { motion } from 'framer-motion';

interface JobDetailViewProps {
  job: Job;
  onClose: () => void;
}

export default function JobDetailView({ job, onClose }: JobDetailViewProps) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/20 backdrop-blur-sm"
        onClick={onClose}
      />
      
      <motion.div 
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 25, stiffness: 200 }}
        className="relative w-full max-w-md bg-card border-l border-border shadow-2xl h-full overflow-y-auto flex flex-col"
      >
        {/* Header */}
        <div className="p-6 border-b border-border flex items-start justify-between sticky top-0 bg-card z-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${job.platform === 'ESP' ? 'bg-red-500/10 text-red-500 border border-red-500/20' : 'bg-green-500/10 text-green-500 border border-green-500/20'}`}>
                {job.platform}
              </span>
              <span className="text-xs text-muted-foreground font-mono">{job.id}</span>
            </div>
            <h2 className="text-xl font-bold text-foreground">{job.product_id}</h2>
            <a 
              href={job.source_link} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-xs text-emerald-500 hover:text-emerald-400 flex items-center gap-1 mt-1"
            >
              View Source Presentation <ExternalLink className="w-3 h-3" />
            </a>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-secondary rounded-full text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-8 flex-1">
          
          {/* Status Section */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Current Status</h3>
              <span className="text-xs text-muted-foreground">Last updated: {new Date(job.updated_at).toLocaleTimeString()}</span>
            </div>
            <div className="bg-secondary/30 rounded-lg p-4 border border-border">
              <div className="flex items-center justify-between mb-4">
                <StatusBadge status={job.status} className="scale-110 origin-left" />
                <span className="font-bold text-xl text-emerald-500">{job.progress}%</span>
              </div>
              <ProgressBar progress={job.progress} showLabel={false} />
            </div>
          </section>

          {/* Key Data Points */}
          <section className="grid grid-cols-2 gap-4">
            <div className="bg-secondary/30 p-3 rounded-lg border border-border">
              <p className="text-xs text-muted-foreground mb-1">Vendor</p>
              <p className="font-medium text-foreground truncate">{job.vendor || 'Pending...'}</p>
            </div>
            <div className="bg-secondary/30 p-3 rounded-lg border border-border">
              <p className="text-xs text-muted-foreground mb-1">MPN</p>
              <p className="font-medium text-foreground font-mono truncate">{job.mpn || 'Pending...'}</p>
            </div>
          </section>

          {/* Action Items */}
          {job.action_items.length > 0 && (
            <section>
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">Action Items</h3>
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
                <ul className="space-y-2">
                  {job.action_items.map((item, idx) => (
                    <li key={idx} className="text-sm text-amber-500 flex items-start gap-2">
                      <span className="mt-1.5 w-1.5 h-1.5 bg-amber-500 rounded-full shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}

          {/* Links & Resources */}
          <section>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">Resources</h3>
            <div className="space-y-2">
              <ResourceLink 
                label="Vendor Website" 
                url={job.vendor_website} 
                icon={<Globe className="w-4 h-4" />} 
                disabled={!job.vendor_website}
              />
              <ResourceLink 
                label="Zoho Item Master" 
                url={job.zoho_item_link} 
                icon={<FileText className="w-4 h-4" />} 
                disabled={!job.zoho_item_link}
              />
              <ResourceLink 
                label="Price Calculator" 
                url={job.calculator_link} 
                icon={<Calculator className="w-4 h-4" />} 
                disabled={!job.calculator_link}
              />
              <ResourceLink 
                label="Zoho Quote" 
                url={job.zoho_quote_link} 
                icon={<ShoppingCart className="w-4 h-4" />} 
                disabled={!job.zoho_quote_link}
                highlight
              />
            </div>
          </section>

          {/* Timeline Stub */}
          <section>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">Timeline</h3>
            <div className="border-l-2 border-border ml-2 space-y-6 pl-6 py-2">
              <TimelineItem time={job.created_at} label="Workflow Initiated" done />
              <TimelineItem time={job.updated_at} label="Platform Identified" done />
              <TimelineItem label="Data Extraction" done={job.progress > 30} />
              <TimelineItem label="Zoho Integration" done={job.progress > 70} />
              <TimelineItem label="Final Quote Generated" done={job.progress === 100} />
            </div>
          </section>

        </div>
      </motion.div>
    </div>
  );
}

function ResourceLink({ label, url, icon, disabled, highlight }: { label: string, url: string | null, icon: React.ReactNode, disabled?: boolean, highlight?: boolean }) {
  if (disabled) {
    return (
      <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/10 opacity-50 cursor-not-allowed">
        <div className="flex items-center gap-3">
          {icon}
          <span className="text-sm font-medium">{label}</span>
        </div>
        <span className="text-xs">Pending</span>
      </div>
    );
  }
  
  return (
    <a 
      href={url!} 
      target="_blank" 
      rel="noopener noreferrer"
      className={`flex items-center justify-between p-3 rounded-lg border transition-all ${highlight ? 'bg-emerald-500/10 border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-500' : 'bg-card border-border hover:bg-secondary text-foreground'}`}
    >
      <div className="flex items-center gap-3">
        {icon}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <ExternalLink className="w-4 h-4 opacity-50" />
    </a>
  );
}

function TimelineItem({ time, label, done }: { time?: string, label: string, done?: boolean }) {
  return (
    <div className="relative">
      <div className={`absolute -left-[31px] top-1 w-4 h-4 rounded-full border-2 ${done ? 'bg-emerald-500 border-emerald-500' : 'bg-background border-border'}`} />
      <p className={`text-sm font-medium ${done ? 'text-foreground' : 'text-muted-foreground'}`}>{label}</p>
      {time && <p className="text-xs text-muted-foreground mt-0.5">{new Date(time).toLocaleTimeString()}</p>}
    </div>
  );
}

