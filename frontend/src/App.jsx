import { Outlet } from "react-router-dom";
import Topbar from "./components/Topbar";
import "./App.css";

function App() {
  return (
    <main className="app-shell">
      <Topbar />

      <Outlet />

      <footer className="footer" id="about">
        <span>⚛️ React + Vite</span>
        <span>🐳 Docker Compose ready</span>
        <span>&lt;/&gt; RetailOps MVP shell</span>
      </footer>
    </main>
  );
}

export default App;