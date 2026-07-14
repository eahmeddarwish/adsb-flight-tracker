# Runs the ADS-B Flight Tracker in simulation mode — no RTL-SDR hardware
# required. This is what Hugging Face Spaces (Docker SDK) builds and runs.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hugging Face Spaces expects the app on port 7860.
ENV PORT=7860
EXPOSE 7860

# start.py launches the Flask server (serves GUI + API) and, in sim mode,
# the simulate.py data source, both on $PORT.
CMD ["python3", "app/start.py"]
