import { createBrowserRouter, Navigate } from "react-router-dom";

import App from "../App.jsx";
import Admin from "../pages/Admin.jsx";
import Anomalies from "../pages/Anomalies.jsx";
import Dashboard from "../pages/Dashboard.jsx";
import Forecasts from "../pages/Forecasts.jsx";
import Product360 from "../pages/Product360.jsx";
import Products from "../pages/Products.jsx";
import Profile from "../pages/Profile.jsx";
import Recommendations from "../pages/Recommendations.jsx";

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
        path: "products/:productId",
        element: <Product360 />,
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
        path: "profile",
        element: <Profile />,
      },
      {
        path: "*",
        element: <Navigate to="/" replace />,
      },
    ],
  },
]);

export default router;
