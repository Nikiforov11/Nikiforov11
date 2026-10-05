# One image for both the worker and the Streamlit app; docker-compose picks
# the command. Python 3.12 slim keeps it small.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data

WORKDIR /app

# Dependencies first: this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Don't run as root.
RUN useradd --create-home analyst && mkdir -p /data && chown analyst:analyst /data
USER analyst

EXPOSE 8000 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
