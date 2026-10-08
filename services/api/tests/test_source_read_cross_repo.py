"""Actual AI client -> loopback HTTP -> source API -> isolated PostgreSQL fixture."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4, uuid5

import psycopg
import pytest
import uvicorn
from pydantic import SecretStr

from app.auth import source_reads as auth
from app.main import app


@pytest.mark.integration_db
def test_pinned_ai_client_real_http_postgres(tmp_path, monkeypatch, database_url):
    root = os.getenv("RETAILOPS_AI_SOURCE_CLIENT_ROOT")
    if not root:
        if os.getenv("REQUIRE_SOURCE_REST_TESTS") == "1":
            pytest.fail("Pinned AI source client is required")
        pytest.skip("Set RETAILOPS_AI_SOURCE_CLIENT_ROOT for the actual cross-repo REST drill")
    source_path = Path(__file__).parents[1] / "app/contracts/source-reads-v2/openapi.json"
    ai_path = Path(root) / "src/retailops_ai/source_rest"
    assert source_path.read_bytes() == (ai_path / "upstream.openapi.json").read_bytes()
    manifest = json.loads(source_path.with_name("client.json").read_text())
    upstream = json.loads((ai_path / "upstream.json").read_text())
    assert upstream["commit"] == manifest["contract_source_commit"]
    assert (
        upstream["sha256"]
        == manifest["contract_sha256"]
        == hashlib.sha256(source_path.read_bytes()).hexdigest()
    )
    sys.path.insert(0, str(Path(root) / "src"))
    monkeypatch.setenv(
        "PYTHONPATH", str(Path(root) / "src") + os.pathsep + os.getenv("PYTHONPATH", "")
    )
    from retailops_ai.source_rest import wire
    from retailops_ai.source_rest.client import (
        ClientConfig,
        SourceClient,
        SourceReadError,
        TraceContext,
    )

    target = urlsplit(database_url)
    disposable = (
        os.getenv("GITHUB_ACTIONS") == "true"
        and target.hostname in ("localhost", "127.0.0.1")
        and target.path == "/retailops"
    )
    owned_local = target.hostname in ("localhost", "127.0.0.1") and target.path.startswith(
        "/retailops_ai10_rest_"
    )
    assert disposable or owned_local, (
        "Cross-repo fixture writes require a disposable CI or dedicated AI10 test database"
    )
    product = uuid4()
    now = datetime.now(UTC)
    token = "explicit-cross-repo-source-fixture-" + uuid4().hex
    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {
                "version": "retailops-source-access-1.0",
                "principals": [
                    {
                        "principal_id": "cross-repo-fixture",
                        "credential_sha256": hashlib.sha256(token.encode()).hexdigest(),
                        "resources": [
                            "products",
                            "sales",
                            "inventory-snapshots",
                            "forecasts",
                            "inventory-risks",
                        ],
                        "product_ids": [str(product)],
                        "channels": ["store"],
                        "warehouse_codes": ["AI10-WH"],
                    }
                ],
            }
        )
    )
    policy.chmod(0o600)
    monkeypatch.setenv("RETAILOPS_SOURCE_ACCESS_POLICY", str(policy))
    auth.access_policy.cache_clear()
    server = None
    thread = None
    listener = None
    try:
        with psycopg.connect(database_url) as db:
            db.execute(
                "INSERT INTO products (id,sku,name,status,created_at,updated_at) VALUES (%s,%s,%s,'active',%s,%s)",
                (
                    product,
                    "AI10-" + product.hex,
                    "Explicit AI10 source mechanics fixture",
                    now - timedelta(minutes=2),
                    now - timedelta(minutes=1),
                ),
            )
            for index in range(125):
                db.execute(
                    "INSERT INTO sales (id,product_id,quantity,sold_at,unit_price,total_amount,currency,channel,created_at) VALUES (%s,%s,3,%s,10,30,'PLN','store',%s)",
                    (
                        uuid5(product, str(index)),
                        product,
                        now - timedelta(hours=1),
                        now - timedelta(minutes=1),
                    ),
                )
            db.execute(
                "INSERT INTO inventory_snapshots (id,product_id,stock_quantity,unit_of_measure,warehouse_code,recorded_at,ingested_at,created_at) VALUES (%s,%s,100,'pcs','AI10-WH',%s,%s,%s)",
                (
                    uuid4(),
                    product,
                    now - timedelta(minutes=3),
                    now - timedelta(minutes=2),
                    now - timedelta(minutes=1),
                ),
            )
            db.execute(
                "INSERT INTO forecasts (id,product_id,forecast_period_start,forecast_period_end,predicted_quantity,unit_of_measure,generated_at,method,status,confidence_level) VALUES (%s,%s,%s,%s,25,'pcs',%s,'seeded_demo','generated',0.9)",
                (
                    uuid4(),
                    product,
                    now.date(),
                    (now + timedelta(days=7)).date(),
                    now - timedelta(minutes=1),
                ),
            )
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="error", access_log=False, lifespan="off")
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        reader = SourceClient(
            ClientConfig(
                base_url="http://127.0.0.1:" + str(port),
                credential=SecretStr(token),
                allow_http_loopback=True,
            )
        )
        trace = TraceContext("cross-repo-source-read", "00-" + "1" * 32 + "-" + "2" * 16 + "-01")
        assert reader.capabilities(trace=trace).value.immutable_snapshot is False
        sales_query = wire.SalesQuery(
            product_id=product,
            channel="store",
            sold_from=now - timedelta(days=1),
            sold_to=now,
            limit=100,
        )
        pages = reader.sales_pages(sales_query, trace=trace)
        assert [len(p.value.items) for p in pages] == [100, 25]
        assert len({item.id for p in pages for item in p.value.items}) == 125
        assert sum(item.quantity for p in pages for item in p.value.items) == 375
        assert all(
            p.metadata.freshness_status == "unknown" and not p.metadata.snapshot_supported
            for p in pages
        )
        empty = reader.sales(
            sales_query.model_copy(
                update={"sold_from": now - timedelta(days=3), "sold_to": now - timedelta(days=2)}
            )
        )
        assert empty.value.items == [] and empty.metadata.freshness_status == "missing"
        one = reader.sales(sales_query.model_copy(update={"limit": 1}))
        assert len(one.value.items) == 1
        assert len(reader.products(wire.ProductsQuery(product_id=product)).value.items) == 1
        inventory = reader.inventory(
            wire.InventoryQuery(
                product_id=product,
                warehouse_code="AI10-WH",
                recorded_from=now - timedelta(days=1),
                recorded_to=now,
            )
        )
        assert (
            inventory.value.items[0].stock_quantity == 100
            and inventory.value.items[0].unit_of_measure == "pcs"
        )
        forecast = reader.forecasts(
            wire.ForecastsQuery(
                product_id=product, date_from=now.date(), date_to=(now + timedelta(days=7)).date()
            )
        )
        assert forecast.value.items[0].predicted_quantity == 25
        assert forecast.value.items[0].method == "seeded_demo"
        assert forecast.metadata.semantics == "legacy_product_period_forecast"
        risk = reader.risks(wire.RisksQuery(product_id=product))
        assert risk.value.items[0].risk_status == "overstock_risk"
        assert risk.metadata.semantics == "legacy_product_heuristic_risk"
        for invalid in ({"product_id": uuid4()}, {"channel": "online"}):
            with pytest.raises(SourceReadError, match="invalid_scope"):
                reader.sales(sales_query.model_copy(update=invalid))
        bad_reader = SourceClient(
            ClientConfig(
                base_url="http://127.0.0.1:" + str(port),
                credential=SecretStr("invalid-test-token-" + "b" * 40),
                allow_http_loopback=True,
            )
        )
        with pytest.raises(SourceReadError, match="unauthorized"):
            bad_reader.capabilities()
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=5)
        if listener is not None:
            listener.close()
        auth.access_policy.cache_clear()
        with psycopg.connect(database_url) as db:
            db.execute("DELETE FROM products WHERE id = %s", (product,))
