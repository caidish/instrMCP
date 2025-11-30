import React from 'react';

interface IconProps {
  className?: string;
}

export const PlayIcon: React.FC<IconProps> = ({ className }) => (
  <svg className={className} viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">
    <path d="M4 3l12 7-12 7V3z" fill="currentColor" />
  </svg>
);

export const StopIcon: React.FC<IconProps> = ({ className }) => (
  <svg className={className} viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">
    <rect x="4" y="4" width="12" height="12" rx="2" fill="currentColor" />
  </svg>
);

export const ShieldIcon: React.FC<IconProps> = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
    <path
      d="M12 3l7 3v5.5c0 3.7-2.9 6.9-7 8.5-4.1-1.6-7-4.8-7-8.5V6l7-3z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    />
  </svg>
);

export const WarningIcon: React.FC<IconProps> = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
    <path
      d="M12 3l9.5 16.5H2.5L12 3z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    />
    <path d="M12 9v4.5" stroke="currentColor" strokeWidth="1.5" />
    <circle cx="12" cy="17" r="1" fill="currentColor" />
  </svg>
);

export const SkullIcon: React.FC<IconProps> = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
    <path
      d="M12 3a7 7 0 00-7 7c0 2.6 1.4 4.8 3.5 6v3l2.5-1.5L13.5 19l2.5 1v-3a7 7 0 003.5-6 7 7 0 00-7-7z"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    />
    <circle cx="9.5" cy="10.5" r="1" fill="currentColor" />
    <circle cx="14.5" cy="10.5" r="1" fill="currentColor" />
    <path d="M10 14h4" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

export const GearIcon: React.FC<IconProps> = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
    <path
      d="M12 9a3 3 0 100 6 3 3 0 000-6zm-7.5 3a7.5 7.5 0 0115 0 7.5 7.5 0 01-15 0zm7.5-9v2m0 14v2m9-9h-2M5 12H3m14.2-7l-1.4 1.4M7.2 16.8L5.8 18.2m0-12.4L7.2 7.2m11 9.6l-1.4-1.4"
      stroke="currentColor"
      strokeWidth="1.2"
      fill="none"
    />
  </svg>
);

export const ChevronIcon: React.FC<IconProps> = ({ className }) => (
  <svg className={className} viewBox="0 0 20 20" width="12" height="12" aria-hidden="true">
    <path d="M6 8l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);
