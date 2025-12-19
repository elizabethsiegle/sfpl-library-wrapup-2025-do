# 1. Use the official Playwright image (has all browsers and Linux libs)
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

# 2. This creates a folder NAMED "app" inside the Docker container
WORKDIR /app

# 3. Copy your requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install-deps                     ║

# 4. Copy everything from your local folder (LIBRARY_WRAPUP) into the container
COPY . .

# 5. Tell Playwright where to find the pre-installed browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONUNBUFFERED=1

# 6. Open the port for DigitalOcean
EXPOSE 8080

# 7. Start the app
CMD ["streamlit", "run", "library_streamlit_app.py", "--server.port", "8080", "--server.address", "0.0.0.0"]