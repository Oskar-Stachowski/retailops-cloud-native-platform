import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { IdentifierText } from "../components/tableCells.jsx";
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
    render: (row) => row.sku || row.product_sku || <IdentifierText value={row.id} />,
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
  {
    header: "Product 360",
    render: (row) => (
      <Link className="inline-link" to={`/products/${row.id}`}>
        Open 360
      </Link>
    ),
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
    return (
      <main className="api-page">
        <LoadingState title="Loading products" />
      </main>
    );
  }

  if (state.error) {
    return (
      <main className="api-page">
        <ErrorState message={state.error.message} onRetry={handleRetry} />
      </main>
    );
  }

  const activeCount = state.products.filter(
    (product) => product.status === "active",
  ).length;

  return (
    <main className="api-page">
      <PageHeader
        eyebrow="Products API"
        title="Product catalog"
        description="Product data is loaded from the backend `/products` endpoint. This page no longer uses local mock data."
      />

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
        description="Product rows link to the Product 360 drill-down view."
        columns={columns}
        rows={state.products}
        getRowKey={(row) => row.id || row.sku}
        emptyMessage="The backend returned no product records. Run database migrations and seed demo data."
      />
    </main>
  );
}
