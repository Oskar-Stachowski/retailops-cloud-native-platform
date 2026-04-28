import { createBrowserRouter, Navigate } from "react-router-dom";
import App from "../App.jsx";
import Dashboard from "../pages/Dashboard.jsx";
import Products from "../pages/Products.jsx";
import Forecasts from "../pages/Forecasts.jsx";
import Anomalies from "../pages/Anomalies.jsx";
import Recommendations from "../pages/Recommendations.jsx";
import Admin from "../pages/Admin.jsx";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: <Dashboard />,
      },
      {
        path: "dashboard",
        element: <Dashboard />,
      },
      {
        path: "products",
        element: <Products />,
      },
      {
        path: "forecasts",
        element: <Forecasts />,
      },
      {
        path: "anomalies",
        element: <Anomalies />,
      },
      {
        path: "recommendations",
        element: <Recommendations />,
      },
      {
        path: "admin",
        element: <Admin />,
      },
      {
        path: "*",
        element: <Navigate to="/" replace />,
      },
    ],
  },
]);

export default router;
