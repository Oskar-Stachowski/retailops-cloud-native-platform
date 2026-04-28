import modules from "./data/modules.json";
import stack from "./data/stack.json";
import "./App.css";

import ApiHealthCard from "./components/ApiHealthCard";
import ModuleGrid from "./components/ModuleGrid";
import Topbar from "./components/Topbar";
import Hero from "./components/Hero";
import StackStatus from "./components/StackStatus";

function App() {
  return (
    <main className="app-shell">
      <Topbar />

      <Hero>
        <ApiHealthCard />
      </Hero>
      
      <StackStatus stack={stack} />

      <ModuleGrid modules={modules} />

      <footer className="footer" id="about">
        <span>⚛️ React + Vite</span>
        <span>🐳 Docker Compose ready</span>
        <span>&lt;/&gt; RetailOps MVP shell</span>
      </footer>
    </main>
  );
}

export default App;