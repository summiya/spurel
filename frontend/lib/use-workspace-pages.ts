"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { isPage, liveError, workspaceFetch } from "@/lib/live-client";
import type { Page } from "@/lib/live-types";

const PAGE_SIZE = 50;

interface PageState<T> {
  key: string | null;
  items: T[];
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  error: string;
}

function initialPage<T>(key: string | null): PageState<T> {
  return {
    key,
    items: [],
    loading: key !== null,
    loadingMore: false,
    hasMore: false,
    error: "",
  };
}

/** Read-only, cancelable pagination for authenticated, explicitly scoped workspace endpoints. */
export function useWorkspacePages<T>(path: string | null) {
  const [state, setState] = useState<PageState<T>>(() => initialPage(path));
  const [revision, setRevision] = useState(0);
  const requestId = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const id = ++requestId.current;

    // Defer the initial state transition to avoid synchronous setState inside an effect.
    void Promise.resolve().then(async () => {
      if (cancelled) return;
      setState(initialPage<T>(path));
      if (path === null) return;
      try {
        const page = await workspaceFetch<Page<T>>(`${path}${path.includes("?") ? "&" : "?"}offset=0`, {
          signal: controller.signal,
        });
        if (!isPage<T>(page)) throw new Error("Unexpected API page response.");
        if (cancelled || id !== requestId.current) return;
        setState({
          key: path,
          items: page.items,
          loading: false,
          loadingMore: false,
          hasMore: page.items.length === PAGE_SIZE,
          error: "",
        });
      } catch (cause) {
        if (cancelled || id !== requestId.current) return;
        setState({
          ...initialPage<T>(path),
          loading: false,
          error: liveError(cause),
        });
      }
    });

    return () => {
      cancelled = true;
      controller.abort();
      requestId.current += 1;
    };
  }, [path, revision]);

  const visible = state.key === path ? state : initialPage<T>(path);

  const refresh = useCallback(() => setRevision((value) => value + 1), []);

  const loadMore = useCallback(async () => {
    if (!path || visible.loading || visible.loadingMore || !visible.hasMore) return;
    const id = ++requestId.current;
    const offset = visible.items.length;
    setState((current) =>
      current.key === path ? { ...current, loadingMore: true, error: "" } : current,
    );
    try {
      const page = await workspaceFetch<Page<T>>(`${path}${path.includes("?") ? "&" : "?"}offset=${offset}`);
      if (!isPage<T>(page)) throw new Error("Unexpected API page response.");
      if (id !== requestId.current) return;
      setState((current) => {
        if (current.key !== path) return current;
        return {
          ...current,
          items: [...current.items, ...page.items],
          loadingMore: false,
          hasMore: page.items.length === PAGE_SIZE,
        };
      });
    } catch (cause) {
      if (id !== requestId.current) return;
      setState((current) =>
        current.key === path
          ? { ...current, loadingMore: false, error: liveError(cause) }
          : current,
      );
    }
  }, [path, visible.loading, visible.loadingMore, visible.hasMore, visible.items.length]);

  return { ...visible, refresh, loadMore };
}
