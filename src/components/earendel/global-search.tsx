"use client";

import * as React from "react";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Icon } from "./icon";
import { api } from "@/lib/earendel/api-client";
import { useStudio } from "@/lib/earendel/store";
import type { SearchResults } from "@/lib/earendel/types";

/**
 * GlobalSearch — a command-palette-style search across actions, connectors,
 * and executions. Wired into the AppShell header. Typing opens a popover
 * with grouped results; selecting a result navigates to the right view.
 */
export function GlobalSearch() {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [results, setResults] = React.useState<SearchResults | null>(null);
  const [loading, setLoading] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const openAction = useStudio((s) => s.openAction);
  const openConnector = useStudio((s) => s.openConnector);
  const openExecution = useStudio((s) => s.openExecution);

  // Debounced search.
  React.useEffect(() => {
    if (!query.trim()) {
      setResults(null);
      return;
    }
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const r = await api.search(query.trim());
        setResults(r);
      } catch {
        setResults(null);
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => clearTimeout(t);
  }, [query]);

  const totalHits =
    (results?.actions.length ?? 0) +
    (results?.connectors.length ?? 0) +
    (results?.executions.length ?? 0);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className="relative w-full">
          <Icon
            name="search"
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => query && setOpen(true)}
            placeholder="Search actions, connectors, executions…"
            aria-label="Search"
            aria-expanded={open}
            className="pl-9"
          />
          {query && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 er-caption text-muted-foreground/60">
              {loading ? "…" : totalHits > 0 ? totalHits : "0"}
            </span>
          )}
        </div>
      </PopoverTrigger>
      <PopoverContent
        className="w-[420px] p-0"
        align="start"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <Command shouldFilter={false} className="rounded-md">
          <CommandList className="max-h-80">
            {!query.trim() ? (
              <div className="p-4 text-center">
                <p className="er-caption text-muted-foreground">
                  Type to search across actions, connectors, and executions.
                </p>
              </div>
            ) : loading ? (
              <div className="p-4 text-center">
                <Icon name="sync" size={16} className="er-pulse inline text-muted-foreground" aria-hidden />
                <p className="er-caption text-muted-foreground mt-1">Searching…</p>
              </div>
            ) : totalHits === 0 ? (
              <CommandEmpty>No results for “{query}”.</CommandEmpty>
            ) : (
              <>
                {results!.actions.length > 0 && (
                  <CommandGroup heading="Actions">
                    {results!.actions.map((a) => (
                      <CommandItem
                        key={a.id}
                        value={`action-${a.id}`}
                        onSelect={() => {
                          openAction(a.id);
                          setOpen(false);
                          setQuery("");
                        }}
                        className="gap-2"
                      >
                        <Icon name="actions" size={14} className="text-accent shrink-0" aria-hidden />
                        <div className="min-w-0 flex-1">
                          <p className="font-mono text-xs text-foreground truncate">{a.signature}</p>
                          <p className="er-caption text-muted-foreground truncate">{a.description}</p>
                        </div>
                        <Badge variant="outline" className="er-pill-neutral text-[10px] capitalize">{a.category}</Badge>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {results!.connectors.length > 0 && (
                  <CommandGroup heading="Connectors">
                    {results!.connectors.map((c) => (
                      <CommandItem
                        key={c.id}
                        value={`connector-${c.id}`}
                        onSelect={() => {
                          openConnector(c.id);
                          setOpen(false);
                          setQuery("");
                        }}
                        className="gap-2"
                      >
                        <Icon name="connectors" size={14} className="text-primary shrink-0" aria-hidden />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs text-foreground truncate">{c.name}</p>
                          <p className="er-caption text-muted-foreground font-mono truncate">{c.targetDomain}</p>
                        </div>
                        <Badge variant="outline" className="er-pill-neutral text-[10px] capitalize">{c.category}</Badge>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {results!.executions.length > 0 && (
                  <CommandGroup heading="Executions">
                    {results!.executions.map((e) => (
                      <CommandItem
                        key={e.id}
                        value={`execution-${e.id}`}
                        onSelect={() => {
                          openExecution(e.id);
                          setOpen(false);
                          setQuery("");
                        }}
                        className="gap-2"
                      >
                        <Icon name="executions" size={14} className="text-chart-4 shrink-0" aria-hidden />
                        <div className="min-w-0 flex-1">
                          <p className="font-mono text-xs text-foreground truncate">{e.actionName}</p>
                          <p className="er-caption text-muted-foreground truncate">
                            {e.status} · {e.adapter.replace("_", " ")} · {e.caller} · {e.durationMs}ms
                          </p>
                        </div>
                        <Badge
                          className={
                            e.status === "success"
                              ? "er-pill-success text-[10px]"
                              : e.status === "failed" || e.status === "degraded"
                                ? "er-pill-danger text-[10px]"
                                : "er-pill-warn text-[10px]"
                          }
                        >
                          {e.status}
                        </Badge>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export default GlobalSearch;
