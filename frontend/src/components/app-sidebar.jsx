import { Users, BarChart3, Waypoints, Pencil } from 'lucide-react';
import { cn } from '../lib/utils';

const nav = [
  { icon: Users, label: 'Customers', active: true, soon: false },
  { icon: BarChart3, label: 'Analytics', active: false, soon: true },
];

export function AppSidebar({ companyName, onEditCompany }) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col bg-sidebar px-4 py-6 text-sidebar-foreground lg:flex sticky top-0 h-screen overflow-y-auto">
      <div className="flex items-center gap-2.5 px-2">
        <div className="flex size-9 items-center justify-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground shrink-0">
          <Waypoints className="size-5" />
        </div>
        <div className="leading-tight min-w-0 flex-1">
          <div className="flex items-center gap-1.5 min-w-0">
            <p className="text-sm font-semibold text-white truncate">{companyName}</p>
            <button
              type="button"
              onClick={onEditCompany}
              className="text-sidebar-foreground/50 hover:text-white transition-colors shrink-0"
              title="Edit company name"
            >
              <Pencil className="size-3" />
            </button>
          </div>
          <p className="text-xs text-sidebar-foreground/60">Autonomous Collections</p>
        </div>
      </div>

      <nav className="mt-8 flex flex-col gap-1">
        <p className="px-3 pb-2 text-[0.7rem] font-semibold tracking-wider text-sidebar-foreground/40 uppercase">
          Workspace
        </p>
        {nav.map((item) => (
          <button
            key={item.label}
            type="button"
            disabled={item.soon}
            className={cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              item.active
                ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                : item.soon
                  ? 'cursor-not-allowed text-sidebar-foreground/40'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
            )}
          >
            <item.icon className="size-4.5" />
            {item.label}
            {item.soon ? (
              <span className="ml-auto rounded-full bg-sidebar-accent px-2 py-0.5 text-[0.65rem] font-medium tracking-wide text-sidebar-foreground/70">
                Coming soon
              </span>
            ) : null}
          </button>
        ))}
      </nav>

      <div className="mt-auto flex flex-col gap-1">
        <div className="flex items-center gap-3 rounded-xl bg-sidebar-accent/60 px-3 py-2.5">
          <div className="flex size-8 items-center justify-center rounded-full bg-sidebar-primary/20 text-xs font-semibold text-white">
            JA
          </div>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm font-medium text-white">Jarvis</p>
            <p className="truncate text-xs text-sidebar-foreground/60">Collections Lead</p>
          </div>
        </div>
      </div>
    </aside>
  );
}