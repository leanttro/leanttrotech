FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expõe a porta 5000
EXPOSE 5000

# Comando para rodar com Gunicorn (Produção)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]