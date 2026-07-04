import { cn } from '../../lib/utils';

const toneStyles = {
  success: 'bg-success/12 text-success ring-1 ring-inset ring-success/25',
  warning: 'bg-warning/15 text-warning-foreground ring-1 ring-inset ring-warning/40',
  destructive: 'bg-destructive/10 text-destructive ring-1 ring-inset ring-destructive/25',
  muted: 'bg-muted text-muted-foreground ring-1 ring-inset ring-border',
  primary: 'bg-primary/10 text-primary ring-1 ring-inset ring-primary/25',
};

export function Badge({ tone = 'muted', className, children }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
        toneStyles[tone],
        className
      )}
    >
      {children}
    </span>
  );
}