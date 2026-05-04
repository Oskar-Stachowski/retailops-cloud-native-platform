import { useCallback, useEffect, useState } from "react";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import StatusBadge from "../components/StatusBadge";
import { getProducts } from "../services/retailopsApi";
import "../styles/api-connected-ui.css";

function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

const columns = [
  {
    header: "SKU",
    accessor: (row) => row.sku || row.product_sku || row.id,
  },
  {
    header: "Name",
    accessor: (row) => row.name || row.product_name,
  },
  {
    header: "Category",
    accessor: "category",
  },
  {
    header: "Brand",
    accessor: "brand",
  },
  {
    header: "Status",
    render: (row) => (
      <StatusBadge status={row.status}>{row.status || "unknown"}</StatusBadge>
    ),
  },
  {
    header: "Updated",
    accessor: (row) => formatDateTime(row.updated_at || row.last_updated_at),
  },
];

export default function Products() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    products: [],
  });

  useEffect(() => {
    let isMounted = true;

    async function loadInitialProducts() {
      try {
        const products = await getProducts();

        if (isMounted) {
          setState({
            loading: false,
            error: null,
            products,
          });
        }
      } catch (error) {
        if (isMounted) {
          setState({
            loading: false,
            error,
            products: [],
          });
        }
      }
    }

    loadInitialProducts();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleRetry = useCallback(async () => {
    setState((current) => ({
      ...current,
      loading: true,
      error: null,
    }));

    try {
      const products = await getProducts();

      setState({
        loading: false,
        error: null,
        products,
      });
    } catch (error) {
      setState({
        loading: false,
        error,
        products: [],
      });
    }
  }, []);

  if (state.loading) {
    return <LoadingState title="Loading products" />;
  }

  if (state.error) {
    return <ErrorState message={state.error.message} onRetry={handleRetry} />;
  }

  const activeCount = state.products.filter(
    (product) => product.status === "active",
  ).length;

  return (
    <main className="api-page">
      <header className="api-page__header">
        <p className="eyebrow">Products API</p>
        <h1>Product catalog</h1>
        <p>
          Product data is loaded from the backend `/products` endpoint. This page
          no longer uses local mock data.
        </p>
      </header>

      <section className="metrics-grid">
        <MetricCard
          label="Products"
          value={state.products.length}
          helper="Rows returned by backend"
          tone="positive"
        />
        <MetricCard
          label="Active"
          value={activeCount}
          helper="Status = active"
          tone="positive"
        />
        <MetricCard
          label="Inactive / other"
          value={state.products.length - activeCount}
          helper="Non-active products"
        />
      </section>

      <DataTable
        title="Backend product records"
        description="This table is intentionally simple for CS-016. Product 360 drill-down belongs to a later task."
        columns={columns}
        rows={state.products}
        emptyMessage="The backend returned no product records. Run database migrations and seed demo data."
      />
    </main>
  );
}