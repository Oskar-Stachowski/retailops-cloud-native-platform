```mermaid
flowchart LR
    A[data/generator/*.py<br/>generator danych demo]
    B[data/demo/*.csv<br/>wygenerowane pliki CSV]
    C[services/api/scripts/seed_demo_data.py<br/>loader CSV -> DB]
    D[(PostgreSQL<br/>demo dataset w bazie)]
    E[services/api/tests/test_seed_data.py<br/>testy seedów]
    F[Pozostałe testy API / DB]
    G[make demo-refresh]
    H[make test]

    G --> A
    A --> B
    G --> C
    B --> C
    C --> D
    H --> E
    H --> F
    E --> D
    F --> D
```