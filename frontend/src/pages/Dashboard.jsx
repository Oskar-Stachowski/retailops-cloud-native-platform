import modules from "../data/modules.json";
import stack from "../data/stack.json";
import Hero from "../components/Hero";
import ApiHealthCard from "../components/ApiHealthCard";
import StackStatus from "../components/StackStatus";
import ModuleGrid from "../components/ModuleGrid";

function Dashboard() {
  return (
    <>
      <Hero>
        <ApiHealthCard />
      </Hero>

      <StackStatus stack={stack} />
      <ModuleGrid modules={modules} />
    </>
  );
}

export default Dashboard;
