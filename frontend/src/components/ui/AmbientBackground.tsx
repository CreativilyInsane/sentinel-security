// frontend/src/components/ui/AmbientBackground.tsx
import React from 'react';

/**
 * Fixed, full-viewport decorative background: a slowly spinning wireframe
 * globe (with a counter-rotating outer ring) plus a soft radar sweep.
 * Purely visual — pointer-events disabled, sits behind all app content.
 */
export const AmbientBackground: React.FC = () => {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden -z-10" aria-hidden="true">
      {/* Wireframe globe, top-right */}
      <div className="absolute -top-40 -right-40 w-[36rem] h-[36rem]">
        <svg
          className="absolute inset-0 w-full h-full opacity-[0.16] animate-spin-slow"
          viewBox="0 0 400 400"
          fill="none"
        >
          <circle cx="200" cy="200" r="150" stroke="rgb(var(--color-primary-400))" strokeWidth="1" />
          <ellipse cx="200" cy="200" rx="150" ry="60" stroke="rgb(var(--color-primary-400))" strokeWidth="1" />
          <ellipse cx="200" cy="200" rx="150" ry="110" stroke="rgb(var(--color-primary-400))" strokeWidth="1" />
          <ellipse cx="200" cy="200" rx="60" ry="150" stroke="rgb(var(--color-accent-400))" strokeWidth="1" />
          <ellipse cx="200" cy="200" rx="110" ry="150" stroke="rgb(var(--color-accent-400))" strokeWidth="1" />
          <circle cx="200" cy="200" r="150" stroke="rgb(var(--color-primary-300))" strokeWidth="1.5" strokeDasharray="3 9" />
        </svg>
        <svg
          className="absolute inset-0 w-full h-full opacity-[0.09] animate-spin-slower"
          viewBox="0 0 400 400"
          fill="none"
        >
          <circle cx="200" cy="200" r="185" stroke="rgb(var(--color-accent-400))" strokeWidth="1" strokeDasharray="2 10" />
          <circle cx="200" cy="200" r="4" fill="rgb(var(--color-primary-300))" />
          <circle cx="200" cy="15" r="3" fill="rgb(var(--color-accent-300))" />
        </svg>
      </div>

      {/* Radar sweep, bottom-left */}
      <div
        className="absolute -bottom-48 -left-48 w-[34rem] h-[34rem] rounded-full opacity-[0.14] animate-spin-slow"
        style={{
          background:
            'conic-gradient(from 0deg, transparent 0%, rgb(var(--color-primary-400)) 6%, transparent 22%, transparent 100%)',
        }}
      />
      <div className="absolute -bottom-48 -left-48 w-[34rem] h-[34rem] rounded-full border border-primary-400/10" />
      <div className="absolute -bottom-48 -left-48 w-[34rem] h-[34rem] rounded-full border border-primary-400/5 scale-75" />

      {/* Drifting ambient glow orbs */}
      <div className="absolute top-1/3 left-1/4 w-72 h-72 bg-primary-600/[0.06] rounded-full blur-3xl animate-float" />
      <div
        className="absolute bottom-1/4 right-1/3 w-80 h-80 bg-accent-600/[0.05] rounded-full blur-3xl animate-float"
        style={{ animationDelay: '2s' }}
      />
    </div>
  );
};
