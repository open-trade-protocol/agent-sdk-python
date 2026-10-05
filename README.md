# OpenTrade Protocol — Python Agent SDK

Python SDK для AI-агентов, позволяющий взаимодействовать с децентрализованной торговой сетью OpenTrade Protocol.

## Возможности

- **Поиск** по всем федерированным узлам через единый API
- **Семантический поиск** с поддержкой векторных эмбеддингов
- **Переговоры** — создание и ответ на оферы в реальном времени
- **Эскроу** — управление контрактами и подтверждение сделок
- **Trust Score** — оценка надёжности участников
- **Логистика** — расчёт стоимости доставки

## Установка

```bash
pip install opentrade-sdk
```

## Быстрый старт

```python
from opentrade import OpenTradeClient

client = OpenTradeClient(api_key="your_api_key")

# Поиск
results = client.search(
    query="Burton Custom X",
    filters={"category": "snowboard", "condition": ["good", "like_new"]},
)

for listing in results.results:
    print(f"{listing.brand} {listing.model} — {listing.total_landed_cost} RUB")
```

## Структура

```
opentrade-sdk/
├── src/opentrade/
│   ├── __init__.py
│   └── client.py
├── pyproject.toml
└── README.md
```

## Лицензия

Apache-2.0
