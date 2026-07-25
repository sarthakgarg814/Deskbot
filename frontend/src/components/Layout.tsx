import { NavLink, Outlet } from "react-router-dom";
import { useTopic } from "../lib/ws";
import type { SystemStatus } from "../lib/api";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/notes", label: "Notes" },
  { to: "/hardware", label: "Hardware" },
  { to: "/settings", label: "Settings" },
];

export default function Layout() {
  const sys = useTopic<SystemStatus>("system");
  const online = sys !== null;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-neutral-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl">🤖</span>
          <span className="font-semibold tracking-tight">DeskBot</span>
          <span className="text-xs text-neutral-500">AI desktop companion</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`h-2 w-2 rounded-full ${online ? "bg-led-working" : "bg-led-error"}`}
          />
          <span className="text-neutral-400">{online ? "live" : "connecting…"}</span>
        </div>
      </header>

      <div className="flex flex-1">
        <nav className="w-44 border-r border-neutral-800 p-3 space-y-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm ${
                  isActive
                    ? "bg-neutral-800 text-white"
                    : "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
