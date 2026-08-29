# Fersie Management Platform (`fersie-app`)

Full-stack Django 5 + HTMX web application (`app.fersie.com`) managing authentication, product inventory, Excel data ingestion (`Planilha Mercadoria_JUNIOR_v2.xlsx`), sales, financial controls, credit card reconciliation, barcode/QR code scanning, label printing (Elgin L42PRO FULL), dynamic HTMX totalizer tables, and an admin-configurable Gemini / Antigravity AI Assistant.

## Key Modules
- **`core`**: Authentication, user permissions, user roles (`fernanda@fersie.com`, `sibele@fersie.com`, `ieda@fersie.com`), dashboard.
- **`inventory`**: Product stock, categories, suppliers, Excel automated import (`Planilha Mercadoria_JUNIOR_v2.xlsx`).
- **`financial`**: Purchases, counter/online sales, operational expenses, accounts receivable, credit card reconciliation.
- **`catalog`**: Visual photo catalog, webcam/USB barcode reader, Elgin label printing (TSPL/EPL/ZPL).
- **`ai_assistant`**: Admin-configurable Gemini / Antigravity AI assistant with natural language queries over sales, inventory, and financial status.

## Directory Structure
```
fersie-app/
├── manage.py
├── requirements.txt
├── fersie_app/
├── core/
├── inventory/
├── financial/
├── catalog/
├── ai_assistant/
├── templates/
├── static/
├── .gitignore
└── README.md
```
