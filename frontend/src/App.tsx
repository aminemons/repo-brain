import {
  BookOpenText,
  BrainCircuit,
  FolderGit2,
  GitBranch,
  MessageCircleQuestion,
  MessagesSquare,
  Moon,
  Network,
  Settings,
  Sun
} from "lucide-react";
import { useCallback, useEffect, useState, type MouseEvent } from "react";

import { AUTH_REQUIRED_EVENT, TOKEN_CHANGED_EVENT } from "./api/auth";
import { API_UNREACHABLE_EVENT } from "./api/http";
import { getHealth } from "./api/repos";
import { AskPage } from "./pages/AskPage";
import { BrainPage } from "./pages/BrainPage";
import { BotPage } from "./pages/BotPage";
import { BotsPage } from "./pages/BotsPage";
import { GraphPage } from "./pages/GraphPage";
import { ReposPage } from "./pages/ReposPage";
import { SettingsPage } from "./pages/SettingsPage";
import { WikiPage } from "./pages/WikiPage";

export type WorkspaceSection = "repos" | "graph" | "wiki" | "ask" | "brain" | "bots" | "settings";
type ThemeMode = "dark" | "light";

const THEME_STORAGE_KEY = "repo-brain.appearance";

export function App() {
  const [selectedRepoId, setSelectedRepoId] = useState(() => routeFromLocation().repoId ?? "");
  const [activeSection, setActiveSection] = useState<WorkspaceSection>(() => routeFromLocation().section);
  const [activeBotId, setActiveBotId] = useState(() => routeFromLocation().botId ?? null);
  const [theme, setTheme] = useState<ThemeMode>(() => readStoredTheme());
  const [authRequired, setAuthRequired] = useState(false);
  const [tokenRevision, setTokenRevision] = useState(0);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [apiChecking, setApiChecking] = useState(false);

  const checkApi = useCallback(async () => {
    setApiChecking(true);
    setApiStatus("checking");
    try {
      await getHealth();
      setApiStatus("online");
    } catch {
      setApiStatus("offline");
    } finally {
      setApiChecking(false);
    }
  }, []);

  useEffect(() => {
    const requireToken = () => setAuthRequired(true);
    const unreachable = () => setApiStatus("offline");
    const tokenChanged = () => {
      setAuthRequired(false);
      setTokenRevision((value) => value + 1);
    };
    window.addEventListener(AUTH_REQUIRED_EVENT, requireToken);
    window.addEventListener(TOKEN_CHANGED_EVENT, tokenChanged);
    window.addEventListener(API_UNREACHABLE_EVENT, unreachable);
    return () => {
      window.removeEventListener(AUTH_REQUIRED_EVENT, requireToken);
      window.removeEventListener(TOKEN_CHANGED_EVENT, tokenChanged);
      window.removeEventListener(API_UNREACHABLE_EVENT, unreachable);
    };
  }, []);

  useEffect(() => { void checkApi(); }, [checkApi]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    const syncRouteFromUrl = () => {
      const route = routeFromLocation();
      setActiveSection(route.section);
      setActiveBotId(route.botId ?? null);
      if (route.repoId) {
        setSelectedRepoId(route.repoId);
      }
    };

    window.addEventListener("hashchange", syncRouteFromUrl);
    window.addEventListener("popstate", syncRouteFromUrl);
    return () => {
      window.removeEventListener("hashchange", syncRouteFromUrl);
      window.removeEventListener("popstate", syncRouteFromUrl);
    };
  }, []);

  const navigateToSection = useCallback(
    (event: MouseEvent<HTMLAnchorElement>, sectionId: WorkspaceSection) => {
      event.preventDefault();
      setActiveSection(sectionId);
      window.history.pushState(null, "", pathForSection(sectionId, selectedRepoId));
    },
    [selectedRepoId]
  );

  const openBot = useCallback((botId: string) => {
    setActiveSection("bots");
    setActiveBotId(botId);
    window.history.pushState(null, "", `/bots/${encodeURIComponent(botId)}`);
  }, []);

  const openBotLibrary = useCallback((event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    setActiveSection("bots");
    setActiveBotId(null);
    window.history.pushState(null, "", "/bots");
  }, []);

  const handleSelectedRepoChange = useCallback(
    (repoId: string) => {
      setSelectedRepoId(repoId);
      window.history.replaceState(null, "", pathForSection(activeSection, repoId));
    },
    [activeSection]
  );

  const openRepoSection = useCallback((repoId: string, section: WorkspaceSection) => {
    setSelectedRepoId(repoId);
    setActiveSection(section);
    window.history.pushState(null, "", pathForSection(section, repoId));
  }, []);

  const nextTheme = theme === "dark" ? "light" : "dark";

  return (
    <main className="app-shell">
      <aside className="app-header">
        <div className="brand-block">
          <div className="brand-mark">
            <Network size={18} />
          </div>
          <div>
            <div className="brand">Repo Brain</div>
            <div className="brand-subtitle">Repository workspace</div>
          </div>
        </div>

        <nav className="top-nav" aria-label="Workspace">
          <a
            className={activeSection === "repos" ? "is-active" : undefined}
            href={pathForSection("repos", selectedRepoId)}
            onClick={(event) => navigateToSection(event, "repos")}
          >
            <FolderGit2 size={15} />
            Repos
          </a>
          <a
            className={activeSection === "graph" ? "is-active" : undefined}
            href={pathForSection("graph", selectedRepoId)}
            onClick={(event) => navigateToSection(event, "graph")}
          >
            <GitBranch size={15} />
            Graph
          </a>
          <a
            className={activeSection === "wiki" ? "is-active" : undefined}
            href={pathForSection("wiki", selectedRepoId)}
            onClick={(event) => navigateToSection(event, "wiki")}
          >
            <BookOpenText size={15} />
            Wiki
          </a>
          <a
            className={activeSection === "ask" ? "is-active" : undefined}
            href={pathForSection("ask", selectedRepoId)}
            onClick={(event) => navigateToSection(event, "ask")}
          >
            <MessageCircleQuestion size={15} />
            Ask
          </a>
          <a
            className={activeSection === "brain" ? "is-active" : undefined}
            href={pathForSection("brain", selectedRepoId)}
            onClick={(event) => navigateToSection(event, "brain")}
          >
            <BrainCircuit size={15} />
            Learn & docs
          </a>
          <a
            className={activeSection === "bots" ? "is-active" : undefined}
            href="/bots"
            onClick={openBotLibrary}
          >
            <MessagesSquare size={15} />
            Bots
          </a>
          <a
            className={activeSection === "settings" ? "is-active" : undefined}
            href={pathForSection("settings", selectedRepoId)}
            onClick={(event) => navigateToSection(event, "settings")}
          >
            <Settings size={15} />
            Settings
          </a>
        </nav>

        <div className="app-sidebar-spacer" />
        <div className="app-sidebar-footer">
          <div className={`api-connectivity is-${apiStatus}`} role="status" aria-live="polite">
            <span className="status-dot" />
            <span>{apiStatus === "online" ? "Service available" : apiStatus === "offline" ? "Service unreachable" : "Checking service…"}</span>
            {apiStatus === "offline" ? <button type="button" disabled={apiChecking} onClick={() => void checkApi()}>{apiChecking ? "Checking…" : "Retry"}</button> : null}
          </div>
          <span>Appearance</span>
          <button
            type="button"
            className="theme-toggle"
            aria-label={`Switch to ${nextTheme} mode`}
            title={`Switch to ${nextTheme} mode`}
            onClick={() => setTheme(nextTheme)}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            <span>{theme === "dark" ? "Light" : "Dark"}</span>
          </button>
        </div>
      </aside>

      <div className="app-main">
        {apiStatus === "offline" ? <div className="app-offline-banner" role="alert"><strong>Repo Brain could not reach its service.</strong><span>Check that the app server is running.</span><button type="button" disabled={apiChecking} onClick={() => void checkApi()}>{apiChecking ? "Checking…" : "Retry"}</button></div> : null}
        {authRequired ? (
          <div className="brain-auth-alert" role="alert">
            API access requires a valid token.
            <a href={pathForSection("settings", selectedRepoId)} onClick={(event) => navigateToSection(event, "settings")}>Open Settings</a>
          </div>
        ) : null}

      <section key={tokenRevision} className={`workspace is-section-${activeSection}`}>
        {activeSection !== "bots" ? (
          <GraphPage
            selectedRepoId={selectedRepoId}
            onSelectedRepoChange={handleSelectedRepoChange}
            isActiveSection={activeSection === "graph"}
          />
        ) : null}
        {activeSection !== "graph" ? (
          <aside className="assistant-rail">
            {activeSection === "repos" ? (
              <ReposPage
                selectedRepoId={selectedRepoId}
                onRepoChange={handleSelectedRepoChange}
                onOpenRepo={openRepoSection}
                isActiveSection
              />
            ) : null}
            {activeSection === "wiki" ? (
              <WikiPage
                selectedRepoId={selectedRepoId}
                onRepoChange={handleSelectedRepoChange}
                isActiveSection
              />
            ) : null}
            {activeSection === "ask" ? (
              <AskPage
                selectedRepoId={selectedRepoId}
                onRepoChange={handleSelectedRepoChange}
                isActiveSection={activeSection === "ask"}
              />
            ) : null}
            {activeSection === "settings" ? (
              <SettingsPage
                selectedRepoId={selectedRepoId}
                onRepoChange={handleSelectedRepoChange}
                isActiveSection
              />
            ) : null}
            {activeSection === "brain" ? (
              <BrainPage selectedRepoId={selectedRepoId} onRepoChange={handleSelectedRepoChange} />
            ) : null}
            {activeSection === "bots" ? (
              activeBotId ? (
                <BotPage key={activeBotId} botId={activeBotId} onOpenLibrary={() => {
                  setActiveBotId(null);
                  window.history.pushState(null, "", "/bots");
                }} />
              ) : (
                <BotsPage onOpenBot={openBot} onOpenRepos={() => openRepoSection("", "repos")} />
              )
            ) : null}
          </aside>
        ) : null}
      </section>
      </div>
    </main>
  );
}

function readStoredTheme(): ThemeMode {
  const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  return storedTheme === "dark" ? "dark" : "light";
}

function routeFromLocation(): { section: WorkspaceSection; repoId?: string; botId?: string } {
  const pathSegments = window.location.pathname.split("/").filter(Boolean).map(decodeURIComponent);
  if (pathSegments[0] === "bots") {
    return { section: "bots", botId: pathSegments[1] };
  }
  if (pathSegments[0] === "repos") {
    const repoId = pathSegments[1];
    const section = coerceSection(pathSegments[2], "graph");
    return repoId ? { section, repoId } : { section: "repos" };
  }
  if (pathSegments[0] === "settings") {
    return { section: "settings" };
  }

  const hash = window.location.hash.replace("#", "");
  return { section: coerceSection(hash, "graph") };
}

function coerceSection(value: string | undefined, fallback: WorkspaceSection): WorkspaceSection {
  const sections: WorkspaceSection[] = ["repos", "graph", "wiki", "ask", "brain", "bots", "settings"];
  return sections.includes(value as WorkspaceSection) ? (value as WorkspaceSection) : fallback;
}

function pathForSection(section: WorkspaceSection, repoId: string): string {
  if (section === "repos") {
    return "/repos";
  }
  if (section === "bots") return "/bots";
  if (repoId) {
    return `/repos/${encodeURIComponent(repoId)}/${section}`;
  }
  return section === "settings" ? "/settings" : `#${section}`;
}
