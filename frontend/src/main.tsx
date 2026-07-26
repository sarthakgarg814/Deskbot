import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Notes from "./pages/Notes";
import Settings from "./pages/Settings";
import Hardware from "./pages/Hardware";
import Camera from "./pages/Camera";
import Wifi from "./pages/Wifi";
import Water from "./pages/Water";
import Calendar from "./pages/Calendar";
import Account from "./pages/Account";
import Login from "./pages/Login";
import { getToken } from "./lib/auth";
import "./index.css";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: "camera", element: <Camera /> },
      { path: "water", element: <Water /> },
      { path: "calendar", element: <Calendar /> },
      { path: "notes", element: <Notes /> },
      { path: "settings", element: <Settings /> },
      { path: "hardware", element: <Hardware /> },
      { path: "wifi", element: <Wifi /> },
      { path: "account", element: <Account /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  if (!authed) return <Login onLogin={() => setAuthed(true)} />;
  return <RouterProvider router={router} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
