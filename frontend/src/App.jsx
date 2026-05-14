import { Outlet } from "react-router-dom";
import Topbar from "./components/Topbar";
import "./App.css";

function App() {
  return (
    <main className="app-shell">
      <Topbar />

      <Outlet />

      <footer className="footer" id="about" aria-label="RetailOps platform footer">
        <span>⚛️ React + Vite</span>
        <span>🔌 API connected</span>
        <span>🐳 Docker Compose ready</span>
        <span>RetailOps operator dashboard</span>
      </footer>
    </main>
  );
}

export default App;
