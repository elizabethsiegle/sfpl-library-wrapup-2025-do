# Change "jammy" to "noble" to get a newer Python version
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

# 2. Set the working directory
WORKDIR /app

# 3. Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install-deps

# 4. Copy your application code
COPY . .

# 5. Environment variables
# This tells Playwright to use the browsers already baked into the image
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONUNBUFFERED=1

# 6. DigitalOcean App Platform typically uses port 8080
EXPOSE 8080

# 7. Start command
CMD ["streamlit", "run", "library_streamlit_app.py", "--server.port", "8080", "--server.address", "0.0.0.0"]