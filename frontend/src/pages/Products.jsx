import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import DataTable from "../components/DataTable";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import MetricCard from "../components/MetricCard";
import { DistributionBars, InsightVisualCard } from "../components/MiniVisualizations";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { IdentifierText } from "../components/tableCells.jsx";
import { getProducts } from "../services/retailopsApi";
import "../styles/api-connected-ui.css";

const ALL_FILTER_VALUE = "all";

const DEFAULT_FILTERS = {
  search: "",
  status: ALL_FILTER_VALUE,
  category: ALL_FILTER_VALUE,
  updatedSort: "desc",
};

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

function normalizeSearchValue(value) {
  return String(value || "").trim().toLowerCase();
}

function getUpdatedAtTimestamp(product) {
  const date = new Date(product.updated_at || product.last_updated_at || product.created_at || 0);

  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function getUniqueSortedValues(products, fieldName) {
  const values = new Set();

  for (const product of products || []) {
    const value = product?.[fieldName];

    if (value) {
      values.add(String(value));
    }
  }

  return Array.from(values).sort((left, right) => left.localeCompare(right));
}

function hasActiveFilters(filters) {
  return (
    normalizeSearchValue(filters.search) !== "" ||
    filters.status !== ALL_FILTER_VALUE ||
    filters.category !== ALL_FILTER_VALUE ||
    filters.updatedSort !== DEFAULT_FILTERS.updatedSort
  );
}

function productMatchesSearch(product, query) {
  if (!query) {
    return true;
  }

  return [product.sku, product.product_sku, product.name, product.product_name, product.brand]
    .some((value) => normalizeSearchValue(value).includes(query));
}

function getFilteredProducts(products, filters) {
  const query = normalizeSearchValue(filters.search);

  return [...(products || [])]
    .filter((product) => productMatchesSearch(product, query))
    .filter((product) => (
      filters.status === ALL_FILTER_VALUE || product.status === filters.status
    ))
    .filter((product) => (
      filters.category === ALL_FILTER_VALUE || product.category === filters.category
    ))
    .sort((left, right) => {
      const direction = filters.updatedSort === "asc" ? 1 : -1;
      const updatedComparison = getUpdatedAtTimestamp(left) - getUpdatedAtTimestamp(right);

      if (updatedComparison !== 0) {
        return updatedComparison * direction;
      }

      return String(left.sku || left.product_sku || "").localeCompare(
        String(right.sku || right.product_sku || ""),
      );
    });
}

function productCategoryItems(products) {
  const counts = new Map();

  for (const product of products || []) {
    const category = product.category || "Uncategorized";
    counts.set(category, (counts.get(category) || 0) + 1);
  }

  return Array.from(counts, ([label, value]) => ({ label, value })).sort(
    (left, right) => right.value - left.value || left.label.localeCompare(right.label),
  );
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
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  useEffect(() => {
    let isMounted = true;

    async function loadInitialProducts() {
      try {
        const products = await getProducts({ sortBy: "updated_at", sortOrder: "desc" });

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
      const products = await getProducts({ sortBy: "updated_at", sortOrder: "desc" });

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

  const updateFilter = useCallback((event) => {
    const { name, value } = event.target;

    setFilters((current) => ({
      ...current,
      [name]: value,
    }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  const categoryOptions = useMemo(
    () => getUniqueSortedValues(state.products, "category"),
    [state.products],
  );
  const statusOptions = useMemo(
    () => getUniqueSortedValues(state.products, "status"),
    [state.products],
  );
  const filteredProducts = useMemo(
    () => getFilteredProducts(state.products, filters),
    [state.products, filters],
  );
  const activeFilters = hasActiveFilters(filters);

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

  const visibleActiveCount = filteredProducts.filter(
    (product) => product.status === "active",
  ).length;

  return (
    <main className="api-page">
      <PageHeader
        eyebrow="Products API"
        title="Product catalog"
        description="Product data is loaded from the backend `/products` endpoint. Frontend filters make the catalog easier to scan without adding heavy UI complexity."
      />

      <section className="metrics-grid">
        <MetricCard
          label="Products"
          value={state.products.length}
          helper="Rows returned by backend"
          tone="neutral"
        />
        <MetricCard
          label="Visible"
          value={filteredProducts.length}
          helper="Rows after current filters"
          tone="neutral"
        />
        <MetricCard
          label="Active visible"
          value={visibleActiveCount}
          helper="Visible rows with status = active"
          tone="neutral"
        />
        <MetricCard
          label="Categories"
          value={categoryOptions.length}
          helper="Unique product categories"
        />
      </section>

      <section className="catalog-controls table-card" aria-label="Product catalog controls">
        <header className="catalog-controls__header">
          <div>
            <h2>Catalog filters</h2>
            <p>Search by SKU, product name or brand. Filter locally on rows returned by the backend.</p>
          </div>
          {activeFilters ? (
            <button className="secondary-button" type="button" onClick={resetFilters}>
              Reset filters
            </button>
          ) : null}
        </header>
        <div className="catalog-controls__grid">
          <label>
            <span>Search</span>
            <input
              name="search"
              type="search"
              value={filters.search}
              onChange={updateFilter}
              placeholder="SKU, name or brand"
              aria-label="Search products by SKU, name or brand"
            />
          </label>
          <label>
            <span>Status</span>
            <select name="status" value={filters.status} onChange={updateFilter}>
              <option value={ALL_FILTER_VALUE}>All statuses</option>
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Category</span>
            <select name="category" value={filters.category} onChange={updateFilter}>
              <option value={ALL_FILTER_VALUE}>All categories</option>
              {categoryOptions.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Sort</span>
            <select name="updatedSort" value={filters.updatedSort} onChange={updateFilter}>
              <option value="desc">Updated newest first</option>
              <option value="asc">Updated oldest first</option>
            </select>
          </label>
        </div>
      </section>

      <section className="mini-visual-grid mini-visual-grid--two">
        <InsightVisualCard
          eyebrow="Catalog mix"
          title="Product category distribution"
          description="A compact category view makes the product page less table-only."
        >
          <DistributionBars
            items={productCategoryItems(filteredProducts)}
            emptyMessage="No product category data available for the current filters."
          />
        </InsightVisualCard>
      </section>

      <DataTable
        title="Backend product records"
        description={`${filteredProducts.length} of ${state.products.length} products shown. Rows link to the Product 360 drill-down view.`}
        columns={columns}
        rows={filteredProducts}
        getRowKey={(row) => row.id || row.sku}
        emptyMessage={
          activeFilters
            ? "No products match the current filters. Clear search or reset filters."
            : "The backend returned no product records. Run database migrations and seed demo data."
        }
      />
    </main>
  );
}
