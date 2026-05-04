import { useEffect, useState } from "react";

function ApiHealthCard() {
    const [apiHealth, setApiHealth] = useState(null);
    const [apiError, setApiError] = useState(null);
    const [isLoadingHealth, setIsLoadingHealth] = useState(true);

    useEffect(() => {
    async function fetchApiHealth() {
        try {
        const response = await fetch("/api/health");

        if (!response.ok) {
            throw new Error(`API returned HTTP ${response.status}`);
        }

        const data = await response.json();
        setApiHealth(data);
        } catch (error) {
        setApiError(error.message);
        } finally {
        setIsLoadingHealth(false);
        }
    }

    fetchApiHealth();
    }, []);

    return (
        <div className="api-health-card" aria-live="polite">
            <div>
                <p className="eyebrow">API health</p>
                <h3>
                {isLoadingHealth
                    ? "Checking API..."
                    : apiHealth?.status === "ok"
                    ? "API is healthy"
                    : "API unavailable"}
                </h3>
            </div>
        
        {apiHealth && (
            <dl className="health-details">
            <div>
                <dt>Status</dt>
                <dd>{apiHealth.status}</dd>
            </div>
            <div>
                <dt>Service</dt>
                <dd>{apiHealth.service}</dd>
            </div>
            <div>
                <dt>Environment</dt>
                <dd>{apiHealth.environment}</dd>
            </div>
            </dl>
        )}

        {apiError && (
            <p className="health-error">
            Could not reach API: {apiError}
            </p>
        )}
        </div>
    );
}

export default ApiHealthCard;