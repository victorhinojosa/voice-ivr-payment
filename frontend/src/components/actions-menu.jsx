import { useEffect, useRef, useState } from 'react';
import { MoreVertical, Pencil, Trash2 } from 'lucide-react';
import { Button } from './ui/button';

export function ActionsMenu({ customer, onEdit, onDelete }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('mousedown', onClick);
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('mousedown', onClick);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <Button
        size="icon-sm"
        variant="outline"
        aria-label={`More actions for ${customer.name}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <MoreVertical className="size-3.5" />
      </Button>
      {open ? (
        <div role="menu" className="absolute right-0 z-20 mt-1 w-36 overflow-hidden rounded-lg border border-border bg-card py-1 shadow-lg">
          <button
            type="button" role="menuitem"
            onClick={() => { setOpen(false); onEdit(customer); }}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-muted"
          >
            <Pencil className="size-3.5 text-muted-foreground" />
            Edit
          </button>
          <button
            type="button" role="menuitem"
            onClick={() => { setOpen(false); onDelete(customer.id); }}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-destructive transition-colors hover:bg-destructive/10"
          >
            <Trash2 className="size-3.5" />
            Delete
          </button>
        </div>
      ) : null}
    </div>
  );
}